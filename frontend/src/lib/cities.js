// Major cities grouped by country name (must match names in countries.js).
// Used by CitySelect to offer cities based on the chosen country.
export const CITIES_BY_COUNTRY = {
  "United States": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "San Francisco", "Seattle", "Boston", "Miami", "Atlanta", "Las Vegas", "Washington", "Denver", "Detroit"],
  "United Kingdom": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool", "Edinburgh", "Bristol", "Sheffield", "Cardiff", "Belfast", "Newcastle", "Nottingham", "Brighton", "Leicester"],
  "Canada": ["Toronto", "Montreal", "Vancouver", "Calgary", "Ottawa", "Edmonton", "Winnipeg", "Quebec City", "Hamilton", "Halifax", "Victoria", "Mississauga"],
  "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast", "Canberra", "Newcastle", "Hobart", "Darwin", "Cairns"],
  "Germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart", "Düsseldorf", "Leipzig", "Dortmund", "Dresden", "Nuremberg", "Bremen"],
  "France": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg", "Bordeaux", "Lille", "Montpellier", "Cannes", "Toulon"],
  "Italy": ["Rome", "Milan", "Naples", "Turin", "Florence", "Venice", "Bologna", "Genoa", "Palermo", "Verona", "Bari", "Catania"],
  "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza", "Málaga", "Bilbao", "Granada", "Palma", "Alicante", "Marbella", "Ibiza"],
  "Portugal": ["Lisbon", "Porto", "Braga", "Coimbra", "Faro", "Funchal", "Cascais", "Sintra", "Aveiro"],
  "Netherlands": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Groningen", "Haarlem", "Tilburg"],
  "Belgium": ["Brussels", "Antwerp", "Ghent", "Bruges", "Liège", "Namur", "Leuven"],
  "Switzerland": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne", "Lucerne", "Lugano", "St. Moritz"],
  "Austria": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt"],
  "Ireland": ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kilkenny"],
  "Sweden": ["Stockholm", "Gothenburg", "Malmö", "Uppsala", "Lund", "Helsingborg"],
  "Norway": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Tromsø", "Drammen"],
  "Denmark": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg"],
  "Finland": ["Helsinki", "Espoo", "Tampere", "Turku", "Oulu", "Rovaniemi"],
  "Iceland": ["Reykjavik", "Kópavogur", "Hafnarfjörður", "Akureyri"],
  "Poland": ["Warsaw", "Kraków", "Łódź", "Wrocław", "Poznań", "Gdańsk", "Katowice"],
  "Czechia": ["Prague", "Brno", "Ostrava", "Plzeň", "Liberec", "Olomouc"],
  "Slovakia": ["Bratislava", "Košice", "Prešov", "Žilina", "Nitra"],
  "Hungary": ["Budapest", "Debrecen", "Szeged", "Miskolc", "Pécs", "Győr"],
  "Romania": ["Bucharest", "Cluj-Napoca", "Timișoara", "Iași", "Constanța", "Brașov"],
  "Bulgaria": ["Sofia", "Plovdiv", "Varna", "Burgas", "Ruse"],
  "Greece": ["Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa", "Rhodes", "Mykonos", "Santorini"],
  "Croatia": ["Zagreb", "Split", "Rijeka", "Dubrovnik", "Zadar", "Osijek"],
  "Serbia": ["Belgrade", "Novi Sad", "Niš", "Kragujevac", "Subotica"],
  "Slovenia": ["Ljubljana", "Maribor", "Celje", "Koper", "Bled"],
  "Ukraine": ["Kyiv", "Kharkiv", "Odesa", "Dnipro", "Lviv", "Zaporizhzhia"],
  "Russia": ["Moscow", "Saint Petersburg", "Novosibirsk", "Yekaterinburg", "Kazan", "Nizhny Novgorod", "Sochi", "Samara"],
  "Belarus": ["Minsk", "Gomel", "Mogilev", "Vitebsk", "Grodno", "Brest"],
  "Lithuania": ["Vilnius", "Kaunas", "Klaipėda", "Šiauliai", "Panevėžys"],
  "Latvia": ["Riga", "Daugavpils", "Liepāja", "Jelgava", "Jūrmala"],
  "Estonia": ["Tallinn", "Tartu", "Narva", "Pärnu", "Kohtla-Järve"],
  "Turkey": ["Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Adana", "Bodrum", "Konya"],
  "Georgia": ["Tbilisi", "Batumi", "Kutaisi", "Rustavi", "Gori"],
  "Armenia": ["Yerevan", "Gyumri", "Vanadzor", "Vagharshapat"],
  "Azerbaijan": ["Baku", "Ganja", "Sumqayit", "Mingachevir"],
  "Kazakhstan": ["Almaty", "Astana", "Shymkent", "Karaganda", "Aktobe"],
  "Uzbekistan": ["Tashkent", "Samarkand", "Bukhara", "Namangan", "Andijan"],
  "United Arab Emirates": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Al Ain", "Ras Al Khaimah", "Fujairah"],
  "Saudi Arabia": ["Riyadh", "Jeddah", "Mecca", "Medina", "Dammam", "Khobar"],
  "Qatar": ["Doha", "Al Rayyan", "Al Wakrah", "Lusail"],
  "Kuwait": ["Kuwait City", "Hawalli", "Salmiya", "Jahra"],
  "Bahrain": ["Manama", "Muharraq", "Riffa", "Isa Town"],
  "Oman": ["Muscat", "Salalah", "Sohar", "Nizwa"],
  "Israel": ["Tel Aviv", "Jerusalem", "Haifa", "Eilat", "Netanya", "Herzliya"],
  "Lebanon": ["Beirut", "Tripoli", "Sidon", "Byblos", "Jounieh"],
  "Jordan": ["Amman", "Zarqa", "Irbid", "Aqaba", "Petra"],
  "Egypt": ["Cairo", "Alexandria", "Giza", "Sharm El Sheikh", "Hurghada", "Luxor"],
  "Morocco": ["Casablanca", "Rabat", "Marrakech", "Fez", "Tangier", "Agadir"],
  "Tunisia": ["Tunis", "Sfax", "Sousse", "Hammamet", "Djerba"],
  "Algeria": ["Algiers", "Oran", "Constantine", "Annaba", "Blida"],
  "Nigeria": ["Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt", "Benin City"],
  "Ghana": ["Accra", "Kumasi", "Tamale", "Takoradi", "Cape Coast"],
  "Kenya": ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"],
  "South Africa": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth", "Bloemfontein"],
  "Ethiopia": ["Addis Ababa", "Dire Dawa", "Mekelle", "Gondar", "Hawassa"],
  "Tanzania": ["Dar es Salaam", "Dodoma", "Arusha", "Mwanza", "Zanzibar City"],
  "Uganda": ["Kampala", "Gulu", "Mbarara", "Jinja", "Entebbe"],
  "India": ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Goa"],
  "Pakistan": ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan"],
  "Bangladesh": ["Dhaka", "Chittagong", "Khulna", "Rajshahi", "Sylhet"],
  "Sri Lanka": ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo"],
  "Nepal": ["Kathmandu", "Pokhara", "Lalitpur", "Biratnagar", "Bhaktapur"],
  "China": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu", "Hangzhou", "Xi'an", "Chongqing"],
  "Hong Kong": ["Central", "Kowloon", "Tsim Sha Tsui", "Causeway Bay", "Mong Kok"],
  "Taiwan": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Hsinchu"],
  "Japan": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya", "Sapporo", "Fukuoka", "Kobe"],
  "South Korea": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Jeju City"],
  "Thailand": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Krabi", "Koh Samui"],
  "Vietnam": ["Ho Chi Minh City", "Hanoi", "Da Nang", "Nha Trang", "Hoi An", "Hue"],
  "Philippines": ["Manila", "Cebu City", "Davao", "Quezon City", "Makati", "Boracay"],
  "Indonesia": ["Jakarta", "Surabaya", "Bandung", "Bali", "Medan", "Yogyakarta"],
  "Malaysia": ["Kuala Lumpur", "George Town", "Johor Bahru", "Ipoh", "Malacca", "Kota Kinabalu"],
  "Singapore": ["Singapore", "Orchard", "Marina Bay", "Sentosa", "Jurong"],
  "Cambodia": ["Phnom Penh", "Siem Reap", "Sihanoukville", "Battambang"],
  "Myanmar": ["Yangon", "Mandalay", "Naypyidaw", "Bagan"],
  "New Zealand": ["Auckland", "Wellington", "Christchurch", "Queenstown", "Hamilton", "Dunedin"],
  "Mexico": ["Mexico City", "Guadalajara", "Monterrey", "Cancún", "Tijuana", "Puebla", "Playa del Carmen"],
  "Brazil": ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza", "Belo Horizonte", "Recife"],
  "Argentina": ["Buenos Aires", "Córdoba", "Rosario", "Mendoza", "La Plata", "Mar del Plata"],
  "Chile": ["Santiago", "Valparaíso", "Viña del Mar", "Concepción", "Antofagasta"],
  "Colombia": ["Bogotá", "Medellín", "Cali", "Cartagena", "Barranquilla"],
  "Peru": ["Lima", "Arequipa", "Cusco", "Trujillo", "Chiclayo"],
  "Venezuela": ["Caracas", "Maracaibo", "Valencia", "Barquisimeto", "Maracay"],
  "Ecuador": ["Quito", "Guayaquil", "Cuenca", "Manta", "Ambato"],
  "Uruguay": ["Montevideo", "Salto", "Punta del Este", "Paysandú"],
  "Paraguay": ["Asunción", "Ciudad del Este", "Encarnación", "San Lorenzo"],
  "Bolivia": ["La Paz", "Santa Cruz", "Cochabamba", "Sucre", "Oruro"],
  "Costa Rica": ["San José", "Liberia", "Tamarindo", "Jacó", "Alajuela"],
  "Panama": ["Panama City", "Colón", "David", "Bocas del Toro"],
  "Dominican Republic": ["Santo Domingo", "Santiago", "Punta Cana", "Puerto Plata", "La Romana"],
  "Cuba": ["Havana", "Santiago de Cuba", "Varadero", "Camagüey", "Trinidad"],
  "Jamaica": ["Kingston", "Montego Bay", "Ocho Rios", "Negril", "Spanish Town"],
};

// Returns the curated list of cities for a country (empty array if none/unknown).
export const citiesForCountry = (country) => CITIES_BY_COUNTRY[country] || [];

// Snap a detected/typed city to the best-matching curated city for a country.
// Returns the canonical curated name when a good match is found, otherwise the
// original detected city (so it can still be used as a custom entry).
export const matchCuratedCity = (detectedCity, country) => {
  const raw = (detectedCity || "").trim();
  if (!raw) return "";
  const list = citiesForCountry(country);
  if (!list.length) return raw;
  const dc = raw.toLowerCase();
  // 1) exact (case-insensitive)
  let hit = list.find((c) => c.toLowerCase() === dc);
  if (hit) return hit;
  // 2) one name contains the other (handles "Dubai City" ↔ "Dubai")
  hit = list.find((c) => {
    const lc = c.toLowerCase();
    return dc.includes(lc) || lc.includes(dc);
  });
  if (hit) return hit;
  // 3) shared first word (handles "New York City" ↔ "New York")
  const dw = dc.split(/[\s,]+/)[0];
  hit = list.find((c) => c.toLowerCase().split(/[\s,]+/)[0] === dw);
  return hit || raw;
};
