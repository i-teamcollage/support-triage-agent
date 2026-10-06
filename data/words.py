"""Word lists for the made-up shop. Every company, carrier, person and product here is fictional."""

SHOP = "Hollinvale Home"

CARRIERS = {"standard": "Veloway Parcel", "express": "Tramline Couriers", "two-person": "Brookhaul"}
TRACKING_PREFIX = {"Veloway Parcel": ("VW", 10), "Tramline Couriers": ("TC", 9), "Brookhaul": ("BH", 8)}

COUNTRIES = {
    "NL": "Netherlands",
    "BE": "Belgium",
    "LU": "Luxembourg",
    "DE": "Germany",
    "FR": "France",
    "AT": "Austria",
    "IE": "Ireland",
    "DK": "Denmark",
    "ES": "Spain",
    "IT": "Italy",
}
# Customers per country, out of 100: the shop sells most in the Benelux and Germany.
COUNTRY_WEIGHTS = {"NL": 24, "BE": 14, "LU": 3, "DE": 20, "FR": 12, "AT": 7, "IE": 6, "DK": 5, "ES": 5, "IT": 4}
# Working days for standard delivery (Veloway Parcel), by country.
STANDARD_DAYS = {
    "NL": (2, 4),
    "BE": (2, 4),
    "LU": (2, 4),
    "DE": (3, 5),
    "FR": (3, 5),
    "AT": (3, 5),
    "IE": (4, 7),
    "DK": (4, 7),
    "ES": (4, 7),
    "IT": (4, 7),
}
EXPRESS_COUNTRIES = ("NL", "BE", "DE")
PAY_LATER_COUNTRIES = ("NL", "BE", "DE", "AT")
ASSEMBLY_COUNTRIES = ("NL", "BE")
NO_LARGE_ITEMS = ("IE",)

FIRST_NAMES = {
    "NL": ["Anouk", "Bram", "Sanne", "Daan", "Fleur", "Joris", "Lotte", "Thijs", "Femke", "Ruben", "Iris", "Sem"],
    "BE": ["Wout", "Elise", "Arne", "Marie", "Lucas", "Ines", "Pieter", "Hanne", "Jens", "Noor"],
    "LU": ["Claire", "Marc", "Anne", "Tom", "Laura"],
    "DE": ["Lukas", "Hannah", "Jonas", "Lea", "Felix", "Mia", "Paul", "Clara", "Moritz", "Johanna"],
    "FR": ["Camille", "Julien", "Manon", "Hugo", "Chloé", "Louis", "Léa", "Théo", "Inès"],
    "AT": ["Lena", "Florian", "Sophie", "Tobias", "Anna", "Maximilian", "Katharina"],
    "IE": ["Aoife", "Cian", "Niamh", "Oisín", "Siobhán", "Conor", "Ciara"],
    "DK": ["Freja", "Mads", "Ida", "Emil", "Clara", "Magnus", "Astrid"],
    "ES": ["Lucía", "Pablo", "Carmen", "Javier", "Elena", "Diego"],
    "IT": ["Giulia", "Marco", "Chiara", "Luca", "Sara", "Matteo"],
}
LAST_NAMES = {
    "NL": ["de Vries", "Visser", "Bakker", "Jansen", "Mulder", "de Boer", "Smit", "Meijer", "van Dijk", "Kok"],
    "BE": ["Peeters", "Janssens", "Maes", "Willems", "Claes", "Goossens", "Wouters", "Dubois", "Lemmens"],
    "LU": ["Schmit", "Weber", "Muller", "Hoffmann", "Wagner"],
    "DE": ["Becker", "Schmitt", "Wagner", "Hoffmann", "Schulz", "Koch", "Richter", "Wolf", "Krüger"],
    "FR": ["Laurent", "Moreau", "Girard", "Bonnet", "Fontaine", "Rousseau", "Lambert", "Mercier"],
    "AT": ["Gruber", "Huber", "Bauer", "Pichler", "Moser", "Steiner", "Hofer"],
    "IE": ["Murphy", "Byrne", "O'Brien", "Walsh", "Kelly", "Ryan", "Doyle"],
    "DK": ["Nielsen", "Jensen", "Hansen", "Pedersen", "Larsen", "Andersen"],
    "ES": ["García", "Martín", "López", "Sánchez", "Romero", "Navarro"],
    "IT": ["Romano", "Ricci", "Conti", "Greco", "Bruno", "Gallo"],
}
CITIES = {
    "NL": ["Utrecht", "Haarlem", "Leiden", "Groningen", "Eindhoven", "Delft", "Zwolle", "Arnhem"],
    "BE": ["Ghent", "Antwerp", "Leuven", "Bruges", "Mechelen", "Namur"],
    "LU": ["Luxembourg", "Esch-sur-Alzette"],
    "DE": ["Cologne", "Hamburg", "Munich", "Leipzig", "Freiburg", "Münster", "Bremen"],
    "FR": ["Lyon", "Nantes", "Lille", "Bordeaux", "Rennes", "Strasbourg"],
    "AT": ["Vienna", "Graz", "Linz", "Salzburg", "Innsbruck"],
    "IE": ["Dublin", "Cork", "Galway", "Limerick"],
    "DK": ["Copenhagen", "Aarhus", "Odense"],
    "ES": ["Madrid", "Valencia", "Seville", "Bilbao"],
    "IT": ["Milan", "Turin", "Bologna", "Florence"],
}

# sku, name, short name a customer would use, price in euros, flags.
# Flags: large (two-person delivery), frame (5-year guarantee), flatpack, hygiene (not returnable once opened),
# measure (made to measure, not returnable), electric, fragile.
PRODUCTS = [
    ("30101", "Alder three-seat sofa, oat bouclé", "sofa", "1149.00", "large frame"),
    ("30102", "Marlow two-seat sofa, forest velvet", "sofa", "899.00", "large frame"),
    ("30103", "Sundby corner sofa, smoke grey", "corner sofa", "1690.00", "large frame"),
    ("30201", "Ashby oak bed frame, 160 x 200", "bed frame", "749.00", "large frame flatpack"),
    ("30202", "Pembury upholstered bed, dusty pink, 140 x 200", "bed", "629.00", "large frame flatpack"),
    ("30301", "Wexley wardrobe, white oak, two doors", "wardrobe", "589.00", "large flatpack"),
    ("30401", "Harlow extendable dining table, walnut", "dining table", "979.00", "large flatpack"),
    ("30402", "Calder round dining table, ash", "dining table", "549.00", "large flatpack"),
    ("30501", "Kenton bookcase, black ash", "bookcase", "219.00", "large flatpack"),
    ("40211", "Ashby oak bedside table", "bedside table", "89.00", "flatpack"),
    ("40212", "Nook side table, terracotta", "side table", "59.00", ""),
    ("40213", "Ravel wall shelf, oak", "wall shelf", "45.00", "flatpack"),
    ("40214", "Pella bar stool, black", "bar stool", "79.00", "flatpack"),
    ("40215", "Orla desk chair, sand", "desk chair", "149.00", "flatpack"),
    ("40216", "Halden shoe bench, oak", "shoe bench", "129.00", "flatpack"),
    ("50101", "Lune glass table lamp", "table lamp", "69.00", "electric fragile"),
    ("50102", "Aster floor lamp, brass", "floor lamp", "139.00", "electric"),
    ("50103", "Pip LED reading light", "reading light", "29.95", "electric"),
    ("51207", "Linen cushion cover, sage", "cushion cover", "19.95", ""),
    ("51208", "Bouclé cushion, cream", "cushion", "24.95", ""),
    ("62210", "Wool throw, mustard", "throw", "49.90", ""),
    ("62211", "Washed linen duvet cover set, clay, 200 x 220", "duvet cover set", "89.00", ""),
    ("62212", "Cotton bath towel set, ink blue", "towel set", "39.90", ""),
    ("63301", "Hollow-fibre pillows, pair", "pillows", "34.90", "hygiene"),
    ("63302", "All-season duvet, 200 x 220", "duvet", "89.00", "hygiene"),
    ("63303", "Memory-foam mattress topper, 160 x 200", "mattress topper", "129.00", "hygiene"),
    ("64401", "Made-to-measure blackout curtains, slate", "curtains", "119.00", "measure"),
    ("70101", "Stoneware dinner plates, set of 4", "plates", "39.90", "fragile"),
    ("70102", "Oak serving board", "serving board", "29.95", ""),
    ("70103", "Glass carafe", "carafe", "19.95", "fragile"),
    ("70104", "Cast-iron casserole, 4 litres", "casserole", "79.00", ""),
    ("80101", "Rattan mirror, 60 cm", "mirror", "69.00", "fragile"),
    ("80102", "Jute rug, 160 x 230", "rug", "149.00", ""),
    ("80103", "Ceramic vase, sand", "vase", "24.95", "fragile"),
    ("80104", "Scented candle, fig", "candle", "16.95", ""),
    ("80105", "Woven storage baskets, set of 2", "storage baskets", "34.95", ""),
]

# For tickets about the wrong colour or size being delivered: the product ordered, how the customer
# describes it, and how they describe what arrived instead.
WRONG_ITEM_SWAPS = [
    ("Linen cushion cover, sage", "sage linen cushion cover", "rust one"),
    ("Wool throw, mustard", "mustard wool throw", "grey throw"),
    ("Washed linen duvet cover set, clay, 200 x 220", "clay duvet cover set", "white duvet cover set"),
    ("Cotton bath towel set, ink blue", "ink blue towel set", "pale pink towel set"),
    ("Orla desk chair, sand", "sand-coloured desk chair", "black desk chair"),
    ("Nook side table, terracotta", "terracotta side table", "olive green side table"),
    ("Jute rug, 160 x 230", "160 x 230 jute rug", "120 x 170 rug"),
]

# Invented company names for business invoices, checked for obvious collisions.
COMPANIES = [
    ("Kesterlind Interiors B.V.", "NL"),
    ("Studio Wavermeer", "NL"),
    ("Atelier Brunelac SARL", "FR"),
    ("Kaffeehaus Lindwacht GmbH", "AT"),
    ("Merelsbeek Architecten BV", "BE"),
    ("Brandtwiese Objektbau GmbH", "DE"),
    ("Glenvarra Design Ltd", "IE"),
]

TIMES_OF_DAY = ["07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22"]
