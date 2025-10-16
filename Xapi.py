import requests

url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
headers = {"X-API-Key": "new1_0635505adb134cce801547ebaa8bd88e"}
params = {"query": "from:PMOIndia", "max_results": 1}

r = requests.get(url, headers=headers, params=params)
print(r.status_code)
print(r.text)
