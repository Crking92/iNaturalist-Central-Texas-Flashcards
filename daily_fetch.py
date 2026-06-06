import requests
import json
from datetime import datetime, timedelta
import os
import time
import csv
from bs4 import BeautifulSoup

script_dir = os.path.dirname(os.path.abspath(__file__))
# Smart folder detection for Windows 'Data' vs 'data'
data_dir = os.path.join(script_dir, 'data')
if not os.path.exists(data_dir) and os.path.exists(os.path.join(script_dir, 'Data')):
    data_dir = os.path.join(script_dir, 'Data')
else:
    os.makedirs(data_dir, exist_ok=True)

MASTER_LIST_FILE = os.path.join(data_dir, 'master_plants.json')
JS_FILE_PATH = os.path.join(data_dir, 'daily_data.js')
HOST_CSV_FILE = os.path.join(data_dir, 'host_numbers.csv')

TARGET_COUNTIES = [
    "Hays County, TX", "Travis County, TX", "Blanco County, TX",
    "Burnet County, TX", "Williamson County, TX", "Bastrop County, TX",
    "Caldwell County, TX", "Guadalupe County, TX", "Comal County, TX"
]

def load_master_list():
    try:
        with open(MASTER_LIST_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {} 

def load_lep_hosts():
    print("🦋 Loading Lepidoptera host data from CSV...")
    hosts = {}
    try:
        with open(HOST_CSV_FILE, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            # Skip the header row
            next(reader, None)
            
            for row in reader:
                # Looking at your file: Column 1 (index 0) is Count, Column 3 (index 2) is Genus
                if len(row) >= 3:
                    count_str = row[0].strip()
                    genus = row[2].strip().capitalize()
                    
                    try:
                        count = int(count_str)
                        if count > 0 and genus:
                            hosts[genus] = count
                    except ValueError:
                        pass
                        
        print(f"   ✓ Successfully loaded {len(hosts)} genera host numbers.")
    except FileNotFoundError:
        print(f"   ⚠️ Could not find {HOST_CSV_FILE}. Ensure it is in the 'data' folder.")
    except Exception as e:
        print(f"   ⚠️ Error reading CSV: {e}")
    return hosts

def get_place_ids():
    print("🌍 Resolving county names to iNaturalist Place IDs...")
    place_ids = []
    for county in TARGET_COUNTIES:
        try:
            url = f"https://api.inaturalist.org/v1/places/autocomplete?q={county.replace(' ', '+')}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    place_ids.append(str(results[0]['id']))
                    print(f"   ✓ Found ID {results[0]['id']} for {county}")
                else:
                    print(f"   ⚠️ Could not resolve {county}")
        except Exception as e:
            print(f"   ⚠️ Error resolving {county}: {e}")
        time.sleep(0.5)
    return place_ids

def scrape_wildflower_data(scientific_name):
    print(f"  🌿 Scrape: Wildflower Center data for {scientific_name}...")
    search_query = scientific_name.replace(' ', '+')
    search_url = f"https://www.wildflower.org/plants/search.php?search_field={search_query}&newsearch=true"
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36', 'Accept': 'text/html' }
    
    traits = { 'wf_photos': [] }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200: return traits

        if 'id_plant=' in response.url:
            profile_soup = BeautifulSoup(response.text, 'html.parser')
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            link = soup.find('a', href=lambda href: href and 'result.php?id_plant=' in href)
            if not link: return traits 
                
            href = link['href'].replace('../', '').replace('..', '')
            profile_url = href if href.startswith('http') else "https://www.wildflower.org/plants/" + href.split('/')[-1]
            profile_response = requests.get(profile_url, headers=headers, timeout=10)
            if profile_response.status_code != 200: return traits
            profile_soup = BeautifulSoup(profile_response.text, 'html.parser')
        
        def extract_trait(header_text):
            bold_tag = profile_soup.find('strong', string=lambda text: text and header_text in text)
            if bold_tag:
                content = []
                for sibling in bold_tag.next_siblings:
                    if sibling.name in ['strong', 'h3', 'div']: break 
                    if sibling.name is None: 
                        txt = sibling.strip().strip(':').strip()
                        if txt: content.append(txt)
                    elif sibling.name == 'a': content.append(sibling.text.strip())
                result = " ".join(content)
                return result if result else "Not Listed"
            return "Not Listed"
            
        traits['duration'] = extract_trait('Duration')
        traits['habit'] = extract_trait('Habit')
        traits['size_notes'] = extract_trait('Size Notes')
        traits['bloom_time'] = extract_trait('Bloom Time')
        traits['bloom_color'] = extract_trait('Bloom Color')
        traits['water_use'] = extract_trait('Water Use')
        traits['light_requirement'] = extract_trait('Light Requirement')
        traits['soil_moisture'] = extract_trait('Soil Moisture')
        traits['native_habitat'] = extract_trait('Native Habitat')
        traits['wildlife'] = extract_trait('Use Wildlife')
        
        wf_photos = []
        for img in profile_soup.find_all('img'):
            src = img.get('src', '')
            if 'imagearchive' in src.lower():
                full_url = "https://www.wildflower.org" + src if src.startswith('/') else src
                wf_photos.append({ 'url': full_url, 'attribution': 'LBJ Wildflower Center' })
        traits['wf_photos'] = wf_photos[:5]

    except Exception:
        pass
    time.sleep(1) 
    return traits

def fetch_taxa_details(taxon_id, scientific_name):
    print(f"  🔍 Fetch: Deep taxonomy and iNaturalist photos for {scientific_name}...")
    details = {'photos': [], 'family': 'Unknown Family'}
    try:
        url = f"https://api.inaturalist.org/v1/taxa/{taxon_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                taxon_data = results[0]
                for ancestor in taxon_data.get('ancestors', []):
                    if ancestor.get('rank') == 'family':
                        details['family'] = ancestor.get('name', 'Unknown Family')
                        break
                for tp in taxon_data.get('taxon_photos', [])[:5]:
                    photo = tp.get('photo', {})
                    img_url = photo.get('medium_url') or photo.get('large_url') or photo.get('original_url') or photo.get('square_url')
                    if img_url:
                        attr = photo.get('attribution', 'Unknown Source').split(',')[0]
                        details['photos'].append({'url': img_url, 'attribution': attr})
    except Exception as e:
        pass
    time.sleep(0.5)
    return details

def fetch_daily_inaturalist_plants(place_ids, lep_hosts):
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    url = "https://api.inaturalist.org/v1/observations"
    new_species_found = {}
    
    for place_id in place_ids:
        print(f"Fetching 30-day iNaturalist data for place ID {place_id}...")
        params = {
            'place_id': place_id, 'taxon_id': 47126, 'quality_grade': 'research',
            'd1': start_date, 'per_page': 200, 'native': 'true' 
        }
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            for obs in data.get('results', []):
                taxon = obs.get('taxon', {})
                scientific_name = taxon.get('name')
                taxon_id = taxon.get('id')
                
                if scientific_name and taxon.get('rank') == 'species' and taxon_id:
                    genus = scientific_name.split()[0].capitalize()
                    lep_count = lep_hosts.get(genus, 0)

                    new_species_found[scientific_name] = {
                        'taxon_id': taxon_id,
                        'common_name': taxon.get('preferred_common_name', 'Unknown'),
                        'family': taxon.get('iconic_taxon_name', 'Unknown'),
                        'lepidoptera': lep_count,
                        'date_added': datetime.now().strftime('%Y-%m-%d')
                    }
    return new_species_found

def update_database():
    master_list = load_master_list()
    place_ids = get_place_ids()
    lep_hosts = load_lep_hosts() 

    print("🔄 Retroactively updating existing plants with new host data...")
    for sci_name, plant_data in master_list.items():
        genus = sci_name.split()[0].capitalize()
        if genus in lep_hosts:
            plant_data['lepidoptera'] = lep_hosts[genus]

    daily_plants = fetch_daily_inaturalist_plants(place_ids, lep_hosts)
    new_discoveries = 0
    
    for scientific_name, plant_data in daily_plants.items():
        if scientific_name not in master_list:
            new_discoveries += 1
            wildflower_traits = scrape_wildflower_data(scientific_name)
            taxa_details = fetch_taxa_details(plant_data['taxon_id'], scientific_name)
            
            plant_data['traits'] = wildflower_traits
            plant_data['photos'] = taxa_details['photos']
            
            if taxa_details['family'] != 'Unknown Family':
                plant_data['family'] = taxa_details['family']
                
            master_list[scientific_name] = plant_data 

    # Always save the file, even if 0 new plants, so the retroactive update saves!
    with open(MASTER_LIST_FILE, 'w') as f:
        json.dump(master_list, f, indent=4)
    with open(JS_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(f"const plantData = {json.dumps(master_list, indent=4)};")
        
    print(f"Finished! {new_discoveries} new species added. Master list updated.")

if __name__ == "__main__":
    update_database()