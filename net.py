import aiohttp
import asyncio
import json
import time
from tqdm import tqdm

# Endpoints
CLAIM_LIST_URL = "https://store.atom.com.mm/mytmapi/v1/my/point-system/claim-list"
CLAIM_URL = "https://store.atom.com.mm/mytmapi/v1/my/point-system/claim"
DASHBOARD_URL = "https://store.atom.com.mm/mytmapi/v1/my/dashboard"
numbers_url = 'https://api.xalyon.xyz/v2/phone'

COMMON_HEADERS = {
    "User-Agent": "MyTM/4.11.0/Android/30",
    "X-Server-Select": "production",
    "Device-Name": "Xiaomi Redmi Note 8 Pro"
}

async def fetch_json_data(session, api_url, db_id):
    """Fetch JSON data from the API and save to backup_{db_id}.json."""
    print(f"Fetching JSON data from API for db {db_id}...")
    try:
        async with session.get(api_url, headers=COMMON_HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                backup_file = f"backup_{db_id}.json"
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print(f"JSON data fetched and saved to {backup_file}.")
                return data
            print(f"Failed to fetch JSON data for db {db_id}. HTTP Code: {response.status}")
            return None
    except Exception as e:
        print(f"Error fetching JSON data for db {db_id}: {str(e)}")
        return None

async def get_claimable_id(session, access_token, msisdn, userid):
    """Get claimable ID from claim-list endpoint."""
    params = {
        "msisdn": msisdn.replace("%2B959", "+959"),
        "userid": userid,
        "v": "4.11.0"
    }
    headers = {**COMMON_HEADERS, "Authorization": f"Bearer {access_token}"}
    try:
        async with session.get(CLAIM_LIST_URL, params=params, headers=headers) as response:
            if response.status == 200:
                json_data = await response.json()
                attributes = json_data.get("data", {}).get("attribute", [])
                for attribute in attributes:
                    if attribute.get("enable", False):
                        return str(attribute.get("id", "no"))
                return "no"
            print(f"[Claim List] {msisdn}: Failed to get claim list - Status {response.status}")
            return "error"
    except Exception as e:
        print(f"[Claim List] Error for {msisdn}: {str(e)}")
        return "error"

async def process_claim(session, access_token, msisdn, userid, claim_id):
    """Process the actual claim with retrieved ID."""
    params = {
        "msisdn": msisdn.replace("%2B959", "+959"),
        "userid": userid,
        "v": "4.11.0"
    }
    headers = {**COMMON_HEADERS, "Authorization": f"Bearer {access_token}"}
    payload = {"id": int(float(claim_id))}  # Handle Java's double parsing logic
    try:
        async with session.post(CLAIM_URL, params=params, json=payload, headers=headers) as response:
            # You can also inspect response_text if needed
            response_text = await response.text()
            status = "Success" if response.status == 200 else "Failed"
            print(f"[Claim] {msisdn}: {status}")
            return status == "Success"
    except Exception as e:
        print(f"[Claim] Error for {msisdn}: {str(e)}")
        return False

async def handle_claim(session, item):
    """Handle complete claim flow for a single item."""
    msisdn = item["phone"]
    access_token = item["access"]
    userid = item["userid"]
    claim_id = await get_claimable_id(session, access_token, msisdn, userid)
    if claim_id == "no":
        print(f"[Claim] {msisdn}: No available claims")
        return False
    if claim_id == "error":
        print(f"[Claim] {msisdn}: Error checking claims")
        return False
    return await process_claim(session, access_token, msisdn, userid, claim_id)

async def refresh_phone_number(session, phone):
    refresh_url = f'https://api.xalyon.xyz/v2/refresh/?phone={phone}'
    async with session.get(refresh_url) as response:
        if response.status == 200:
            print(f'Successfully refreshed data for phone number: {phone}')
        else:
            print(f'Failed to refresh data for phone number: {phone}. Status code: {response.status}')

async def fetch_and_process_phone_numbers():
    async with aiohttp.ClientSession() as session:
        async with session.get(numbers_url) as response:
            if response.status == 200:
                phone_numbers = await response.json()
                if isinstance(phone_numbers, list):
                    # If desired, you can split or process the list as needed.
                    tasks = [refresh_phone_number(session, phone) for phone in phone_numbers]
                    for _ in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing phone numbers"):
                        await _
                else:
                    print('The response is not a list of phone numbers.')
            else:
                print(f'Failed to fetch phone numbers. Status code: {response.status}')

async def send_dashboard_request(session, item):
    """Send dashboard request with custom headers."""
    params = {
        "isFirstTime": "1",
        "isFirstInstall": "0",
        "msisdn": item["phone"].replace("%2B959", "+959"),
        "userid": item["userid"],
        "v": "4.11.0"
    }
    headers = {**COMMON_HEADERS, "Authorization": f"Bearer {item['access']}"}
    try:
        async with session.get(DASHBOARD_URL, params=params, headers=headers) as response:
            # Optionally, inspect response_text here
            response_text = await response.text()
            status = "Success" if response.status == 200 else "Failed"
            print(f"[Dashboard] {item['phone']}: {status}")
    except Exception as e:
        print(f"[Dashboard] Error for {item['phone']}: {str(e)}")

async def process_api_requests_for_db(db_id):
    """Process dashboard and claim requests for a single db_id."""
    # Build the API URL using the current db_id
    api_url = f"https://api.xalyon.xyz/v2/get/?r={db_id}"
    # First, fetch the JSON data from the API for this db
    async with aiohttp.ClientSession() as session:
        json_data = await fetch_json_data(session, api_url, db_id)
        if not json_data:
            print(f"No data to process for db {db_id}. Skipping...")
            return

    # Next, process dashboard and claim requests using the fetched data
    async with aiohttp.ClientSession() as session:
        print(f"\nStarting dashboard requests for db {db_id}...")
        dashboard_tasks = [send_dashboard_request(session, item) for item in json_data]
        await asyncio.gather(*dashboard_tasks)
        print(f"\nAll dashboard requests completed for db {db_id}!")

        print(f"\nStarting claim processes for db {db_id}...")
        claim_tasks = [handle_claim(session, item) for item in json_data]
        await asyncio.gather(*claim_tasks)
        print(f"\nAll claim processes completed for db {db_id}!")

async def run_all():
    """Run all tasks: process each db one by one, then refresh phone numbers."""
    # Define the list of db IDs you want to process.
    db_ids = [1, 2, 3, 4]  # Adjust this list as needed
    for db_id in db_ids:
        await process_api_requests_for_db(db_id)
    # After processing all databases, refresh phone numbers.
    await fetch_and_process_phone_numbers()

if __name__ == "__main__":
    start_time = time.time()
    print("Script execution started...")
    
    asyncio.run(run_all())
    
    print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
    print("Script execution completed.")
