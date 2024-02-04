import requests
from tinydb import TinyDB, Query


def user_exists(user_id: str, db: TinyDB, query: Query) -> bool:
    user = db.get(query["user_id"] == user_id)
    if user:
        return True
    else:
        return False


async def get_strava_refresh_token(user_id: str, client_id: str, client_secret: str, db: TinyDB, query: Query) -> str:
    refresh_token = db.get(query["user_id"] == user_id)["refresh_token"]
    if not refresh_token:
        url = f"https://www.strava.com/api/v3/oauth/token"
        code = db.get(query["user_id"] == user_id)["auth_code"]
        params = {
            "client_id": f"{client_id}",
            "client_secret": f"{client_secret}",
            "grant_type": "authorization_code",
            "code": f"{code}",
        }
        response = requests.post(url, params=params)
        refresh_token = response.json()["refresh_token"]
    return refresh_token


async def get_strava_access_token(user_id: str, client_id: str, client_secret: str, refresh_token: str, db: TinyDB, query: Query) -> str:
    url = f"https://www.strava.com/api/v3/oauth/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(url, params=params)
    refresh_token = response.json()["refresh_token"]
    db.update({"refresh_token": str(refresh_token)}, query["user_id"] == user_id)
    access_token = response.json()["access_token"]
    return access_token


async def post_strava_activity(access_token: str, data_type: str, file: bytes) -> str:
    url = "https://www.strava.com/api/v3/uploads"
    params = {
        "description": "t.me/StravaUploadActivityBot",
        "data_type": data_type,
        "sport_type": "Run",  # HACK
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    files = {"file": file}
    response = requests.post(url, params=params, headers=headers, files=files)
    upload_id = response.json()["id_str"]
    return upload_id


async def get_strava_upload(upload_id: str, access_token: str, statuses: dict):
    url = f"https://www.strava.com/api/v3/uploads/{upload_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        upload = requests.get(url, headers=headers).json()
        if upload["status"] != statuses["wait"]:
            return upload


async def get_strava_activity(access_token: str, activity_id: str) -> str:
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    activity_params = {
        "name": response.json()["name"],
        "sport_type": response.json()["sport_type"],
        "gear": response.json()["gear"]["name"],
        "moving_time": response.json()["moving_time"],
        "distance": response.json()["distance"],
        "description": response.json()["description"],
    }
    return activity_params


async def get_strava_gear(access_token: str) -> str:
    url = "https://www.strava.com/api/v3/athlete"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    gear_list = []
    shoes = response.json()["shoes"]
    bikes = response.json()["bikes"]
    for i in range(len(shoes)):
        shoes[i]["type"] = "👟"
        gear_list.append(shoes[i])
    for i in range(len(bikes)):
        bikes[i]["type"] = "🚲"
        gear_list.append(bikes[i])
    return gear_list


async def update_strava_activity(
    access_token: str, activity_id: str, description: str = None, name: str = None, sport_type: str = None, gear_id: str = None
) -> str:
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    params = {
        key: value
        for key, value in (
            ("description", description),
            ("name", name),
            ("sport_type", sport_type),
            ("gear_id", gear_id),
        )
        if value is not None
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    requests.put(url, params=params, headers=headers)
    response = requests.get(url, headers=headers)
    activity_params = {
        "name": response.json()["name"],
        "sport_type": response.json()["sport_type"],
        "gear": response.json()["gear"]["name"],
        "moving_time": response.json()["moving_time"],
        "distance": response.json()["distance"],
        "description": response.json()["description"],
    }
    return activity_params


async def strava_deauthorize(access_token: str):
    url = "https://www.strava.com/oauth/deauthorize"
    headers = {"Authorization": f"Bearer {access_token}"}
    requests.post(url, headers=headers)
