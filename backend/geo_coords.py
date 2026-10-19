"""Approximate geo-coordinates so EVERY registered user can show a rough distance,
even when they never shared precise GPS (they only picked a country/city).

Resolution order used by approx_coords():
  1. precise lat/lng on the user (from "Detect my location")
  2. CITY_COORDS[country][city]  — major-city centroid
  3. COUNTRY_COORDS[country]     — country centroid (guarantees a value for everyone)
"""

# Country centroids / capitals (lat, lng) for every curated country.
COUNTRY_COORDS = {
    "United States": (39.83, -98.58), "United Kingdom": (51.51, -0.13), "Canada": (56.13, -106.35),
    "Australia": (-25.27, 133.78), "Germany": (51.17, 10.45), "France": (46.60, 2.35),
    "Italy": (41.87, 12.57), "Spain": (40.46, -3.75), "Portugal": (39.40, -8.22),
    "Netherlands": (52.13, 5.29), "Belgium": (50.50, 4.47), "Switzerland": (46.82, 8.23),
    "Austria": (47.52, 14.55), "Ireland": (53.41, -8.24), "Sweden": (60.13, 18.64),
    "Norway": (60.47, 8.47), "Denmark": (56.26, 9.50), "Finland": (61.92, 25.75),
    "Iceland": (64.96, -19.02), "Poland": (51.92, 19.15), "Czechia": (49.82, 15.47),
    "Slovakia": (48.67, 19.70), "Hungary": (47.16, 19.50), "Romania": (45.94, 24.97),
    "Bulgaria": (42.73, 25.49), "Greece": (39.07, 21.82), "Croatia": (45.10, 15.20),
    "Serbia": (44.02, 21.01), "Slovenia": (46.15, 14.99), "Ukraine": (48.38, 31.17),
    "Russia": (55.75, 37.62), "Belarus": (53.71, 27.95), "Lithuania": (55.17, 23.88),
    "Latvia": (56.88, 24.60), "Estonia": (58.60, 25.01), "Turkey": (38.96, 35.24),
    "Georgia": (42.32, 43.36), "Armenia": (40.07, 45.04), "Azerbaijan": (40.14, 47.58),
    "Kazakhstan": (48.02, 66.92), "Uzbekistan": (41.38, 64.59), "United Arab Emirates": (24.47, 54.37),
    "Saudi Arabia": (23.89, 45.08), "Qatar": (25.35, 51.18), "Kuwait": (29.31, 47.48),
    "Bahrain": (26.07, 50.56), "Oman": (21.51, 55.92), "Israel": (31.05, 34.85),
    "Lebanon": (33.85, 35.86), "Jordan": (30.59, 36.24), "Egypt": (26.82, 30.80),
    "Morocco": (31.79, -7.09), "Tunisia": (33.89, 9.54), "Algeria": (28.03, 1.66),
    "Nigeria": (9.08, 8.68), "Ghana": (7.95, -1.02), "Kenya": (-0.02, 37.91),
    "South Africa": (-30.56, 22.94), "Ethiopia": (9.15, 40.49), "Tanzania": (-6.37, 34.89),
    "Uganda": (1.37, 32.29), "India": (20.59, 78.96), "Pakistan": (30.38, 69.35),
    "Bangladesh": (23.68, 90.36), "Sri Lanka": (7.87, 80.77), "Nepal": (28.39, 84.12),
    "China": (35.86, 104.20), "Hong Kong": (22.32, 114.17), "Taiwan": (23.70, 120.96),
    "Japan": (36.20, 138.25), "South Korea": (35.91, 127.77), "Thailand": (15.87, 100.99),
    "Vietnam": (14.06, 108.28), "Philippines": (12.88, 121.77), "Indonesia": (-0.79, 113.92),
    "Malaysia": (4.21, 101.98), "Singapore": (1.35, 103.82), "Cambodia": (12.57, 104.99),
    "Myanmar": (21.91, 95.96), "New Zealand": (-40.90, 174.89), "Mexico": (23.63, -102.55),
    "Brazil": (-14.24, -51.93), "Argentina": (-38.42, -63.62), "Chile": (-35.68, -71.54),
    "Colombia": (4.57, -74.30), "Peru": (-9.19, -75.02), "Venezuela": (6.42, -66.59),
    "Ecuador": (-1.83, -78.18), "Uruguay": (-32.52, -55.77), "Paraguay": (-23.44, -58.44),
    "Bolivia": (-16.29, -63.59), "Costa Rica": (9.75, -83.75), "Panama": (8.54, -80.78),
    "Dominican Republic": (18.74, -70.16), "Cuba": (21.52, -77.78), "Jamaica": (18.11, -77.30),
}

# Major-city coordinates (lat, lng) for better accuracy where we know them.
CITY_COORDS = {
    "United States": {
        "New York": (40.71, -74.01), "Los Angeles": (34.05, -118.24), "Chicago": (41.88, -87.63),
        "Houston": (29.76, -95.37), "Phoenix": (33.45, -112.07), "Philadelphia": (39.95, -75.17),
        "San Antonio": (29.42, -98.49), "San Diego": (32.72, -117.16), "Dallas": (32.78, -96.80),
        "San Jose": (37.34, -121.89), "Austin": (30.27, -97.74), "San Francisco": (37.77, -122.42),
        "Seattle": (47.61, -122.33), "Boston": (42.36, -71.06), "Miami": (25.76, -80.19),
        "Atlanta": (33.75, -84.39), "Las Vegas": (36.17, -115.14), "Washington": (38.90, -77.04),
        "Denver": (39.74, -104.99), "Detroit": (42.33, -83.05),
    },
    "United Kingdom": {
        "London": (51.51, -0.13), "Manchester": (53.48, -2.24), "Birmingham": (52.49, -1.89),
        "Leeds": (53.80, -1.55), "Glasgow": (55.86, -4.25), "Liverpool": (53.41, -2.99),
        "Edinburgh": (55.95, -3.19), "Bristol": (51.45, -2.59), "Sheffield": (53.38, -1.47),
        "Cardiff": (51.48, -3.18), "Belfast": (54.60, -5.93), "Newcastle": (54.98, -1.61),
        "Nottingham": (52.95, -1.15), "Brighton": (50.82, -0.14), "Leicester": (52.64, -1.13),
    },
    "Canada": {
        "Toronto": (43.65, -79.38), "Montreal": (45.50, -73.57), "Vancouver": (49.28, -123.12),
        "Calgary": (51.05, -114.07), "Ottawa": (45.42, -75.70), "Edmonton": (53.55, -113.49),
        "Winnipeg": (49.90, -97.14), "Quebec City": (46.81, -71.21), "Hamilton": (43.26, -79.87),
        "Halifax": (44.65, -63.58), "Victoria": (48.43, -123.37), "Mississauga": (43.59, -79.64),
    },
    "Australia": {
        "Sydney": (-33.87, 151.21), "Melbourne": (-37.81, 144.96), "Brisbane": (-27.47, 153.03),
        "Perth": (-31.95, 115.86), "Adelaide": (-34.93, 138.60), "Gold Coast": (-28.02, 153.40),
        "Canberra": (-35.28, 149.13), "Hobart": (-42.88, 147.33), "Darwin": (-12.46, 130.84),
        "Cairns": (-16.92, 145.77),
    },
    "Germany": {
        "Berlin": (52.52, 13.40), "Munich": (48.14, 11.58), "Hamburg": (53.55, 9.99),
        "Frankfurt": (50.11, 8.68), "Cologne": (50.94, 6.96), "Stuttgart": (48.78, 9.18),
        "Düsseldorf": (51.23, 6.78), "Leipzig": (51.34, 12.37), "Dortmund": (51.51, 7.47),
        "Dresden": (51.05, 13.74), "Nuremberg": (49.45, 11.08), "Bremen": (53.08, 8.80),
    },
    "France": {
        "Paris": (48.86, 2.35), "Marseille": (43.30, 5.37), "Lyon": (45.76, 4.84),
        "Toulouse": (43.60, 1.44), "Nice": (43.70, 7.27), "Nantes": (47.22, -1.55),
        "Strasbourg": (48.57, 7.75), "Bordeaux": (44.84, -0.58), "Lille": (50.63, 3.06),
        "Montpellier": (43.61, 3.88), "Cannes": (43.55, 7.02), "Toulon": (43.12, 5.93),
    },
    "Italy": {
        "Rome": (41.90, 12.50), "Milan": (45.46, 9.19), "Naples": (40.85, 14.27),
        "Turin": (45.07, 7.69), "Florence": (43.77, 11.26), "Venice": (45.44, 12.32),
        "Bologna": (44.49, 11.34), "Genoa": (44.41, 8.93), "Palermo": (38.12, 13.36),
        "Verona": (45.44, 10.99), "Bari": (41.12, 16.87), "Catania": (37.51, 15.08),
    },
    "Spain": {
        "Madrid": (40.42, -3.70), "Barcelona": (41.39, 2.17), "Valencia": (39.47, -0.38),
        "Seville": (37.39, -5.99), "Zaragoza": (41.65, -0.89), "Málaga": (36.72, -4.42),
        "Bilbao": (43.26, -2.93), "Granada": (37.18, -3.60), "Palma": (39.57, 2.65),
        "Alicante": (38.35, -0.49), "Marbella": (36.51, -4.89), "Ibiza": (38.91, 1.43),
    },
    "Portugal": {
        "Lisbon": (38.72, -9.14), "Porto": (41.16, -8.63), "Braga": (41.55, -8.43),
        "Coimbra": (40.20, -8.41), "Faro": (37.02, -7.93), "Funchal": (32.65, -16.91),
        "Cascais": (38.70, -9.42), "Sintra": (38.80, -9.38), "Aveiro": (40.64, -8.65),
    },
    "Netherlands": {
        "Amsterdam": (52.37, 4.90), "Rotterdam": (51.92, 4.48), "The Hague": (52.08, 4.30),
        "Utrecht": (52.09, 5.12), "Eindhoven": (51.44, 5.48), "Groningen": (53.22, 6.57),
        "Haarlem": (52.38, 4.64), "Tilburg": (51.56, 5.09),
    },
    "Belgium": {
        "Brussels": (50.85, 4.35), "Antwerp": (51.22, 4.40), "Ghent": (51.05, 3.72),
        "Bruges": (51.21, 3.22), "Liège": (50.63, 5.57), "Namur": (50.47, 4.87), "Leuven": (50.88, 4.70),
    },
    "Switzerland": {
        "Zurich": (47.37, 8.54), "Geneva": (46.20, 6.14), "Basel": (47.56, 7.59),
        "Bern": (46.95, 7.45), "Lausanne": (46.52, 6.63), "Lucerne": (47.05, 8.31),
        "Lugano": (46.00, 8.95), "St. Moritz": (46.50, 9.84),
    },
    "Russia": {
        "Moscow": (55.75, 37.62), "Saint Petersburg": (59.93, 30.34), "Novosibirsk": (55.01, 82.93),
        "Yekaterinburg": (56.84, 60.65), "Kazan": (55.79, 49.12), "Nizhny Novgorod": (56.30, 43.94),
        "Sochi": (43.60, 39.73), "Samara": (53.20, 50.15),
    },
    "Turkey": {
        "Istanbul": (41.01, 28.98), "Ankara": (39.93, 32.86), "Izmir": (38.42, 27.14),
        "Bursa": (40.19, 29.06), "Antalya": (36.90, 30.71), "Adana": (37.00, 35.32),
        "Bodrum": (37.03, 27.43), "Konya": (37.87, 32.48),
    },
    "United Arab Emirates": {
        "Dubai": (25.20, 55.27), "Abu Dhabi": (24.45, 54.38), "Sharjah": (25.35, 55.39),
    },
    "India": {
        "Mumbai": (19.08, 72.88), "Delhi": (28.70, 77.10), "Bangalore": (12.97, 77.59),
        "Hyderabad": (17.39, 78.49), "Chennai": (13.08, 80.27), "Kolkata": (22.57, 88.36),
        "Pune": (18.52, 73.86), "Goa": (15.30, 74.12),
    },
    "China": {
        "Beijing": (39.90, 116.41), "Shanghai": (31.23, 121.47), "Guangzhou": (23.13, 113.26),
        "Shenzhen": (22.54, 114.06), "Chengdu": (30.57, 104.07), "Hangzhou": (30.27, 120.15),
    },
    "Japan": {
        "Tokyo": (35.68, 139.69), "Osaka": (34.69, 135.50), "Kyoto": (35.01, 135.77),
        "Yokohama": (35.44, 139.64), "Nagoya": (35.18, 136.91), "Fukuoka": (33.59, 130.40),
        "Sapporo": (43.06, 141.35),
    },
    "Brazil": {
        "São Paulo": (-23.55, -46.63), "Rio de Janeiro": (-22.91, -43.17), "Brasília": (-15.79, -47.88),
        "Salvador": (-12.97, -38.51), "Fortaleza": (-3.73, -38.52), "Belo Horizonte": (-19.92, -43.94),
    },
    "Mexico": {
        "Mexico City": (19.43, -99.13), "Guadalajara": (20.66, -103.35), "Monterrey": (25.69, -100.32),
        "Cancún": (21.16, -86.85), "Tijuana": (32.51, -117.04),
    },
}


def approx_coords(user: dict):
    """Best-effort (lat, lng) for a user. Returns (None, None) only if we can't place them."""
    if not user:
        return (None, None)
    lat, lng = user.get("lat"), user.get("lng")
    if lat is not None and lng is not None:
        return (float(lat), float(lng))
    country = (user.get("country") or "").strip()
    city = (user.get("city") or "").strip()
    if country in CITY_COORDS and city in CITY_COORDS[country]:
        return CITY_COORDS[country][city]
    if country in COUNTRY_COORDS:
        return COUNTRY_COORDS[country]
    return (None, None)
