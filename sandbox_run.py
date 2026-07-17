import urllib.request
import json

url = "https://api.coindesk.com/v1/bpi/currentprice.json"

response = urllib.request.urlopen(url)

data = response.read().decode()

json_data = json.loads(data)

usd_price = float(json_data["bpi"]["USD"]["price"].replace(",", ""))

print(usd_price)
