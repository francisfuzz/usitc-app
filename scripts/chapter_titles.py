#!/usr/bin/env python3
"""HTS chapter titles and database enrichment.

The USITC API does not provide chapter titles — only "Chapter XX" placeholders.
This module provides the official titles from the Harmonized Tariff Schedule
and a function to update them in the database.

Usage:
    python scripts/chapter_titles.py [db_path]
    # default: data/hts.db
"""

import sqlite3
import sys

# Official HTS chapter titles (Harmonized System)
HTS_CHAPTER_TITLES = {
    "01": "Live Animals",
    "02": "Meat and Edible Meat Offal",
    "03": "Fish and Crustaceans, Molluscs and Other Aquatic Invertebrates",
    "04": "Dairy Produce; Birds' Eggs; Natural Honey; Edible Products of Animal Origin, Not Elsewhere Specified or Included",
    "05": "Products of Animal Origin, Not Elsewhere Specified or Included",
    "06": "Live Trees and Other Plants; Bulbs, Roots and the Like; Cut Flowers and Ornamental Foliage",
    "07": "Edible Vegetables and Certain Roots and Tubers",
    "08": "Edible Fruit and Nuts; Peel of Citrus Fruit or Melons",
    "09": "Coffee, Tea, Mate and Spices",
    "10": "Cereals",
    "11": "Products of the Milling Industry; Malt; Starches; Inulin; Wheat Gluten",
    "12": "Oil Seeds and Oleaginous Fruits; Miscellaneous Grains, Seeds and Fruit; Industrial or Medicinal Plants; Straw and Fodder",
    "13": "Lac; Gums, Resins and Other Vegetable Saps and Extracts",
    "14": "Vegetable Plaiting Materials; Vegetable Products Not Elsewhere Specified or Included",
    "15": "Animal or Vegetable Fats and Oils and Their Cleavage Products; Prepared Edible Fats; Animal or Vegetable Waxes",
    "16": "Preparations of Meat, of Fish or of Crustaceans, Molluscs or Other Aquatic Invertebrates",
    "17": "Sugars and Sugar Confectionery",
    "18": "Cocoa and Cocoa Preparations",
    "19": "Preparations of Cereals, Flour, Starch or Milk; Pastrycooks' Products",
    "20": "Preparations of Vegetables, Fruit, Nuts or Other Parts of Plants",
    "21": "Miscellaneous Edible Preparations",
    "22": "Beverages, Spirits and Vinegar",
    "23": "Residues and Waste from the Food Industries; Prepared Animal Fodder",
    "24": "Tobacco and Manufactured Tobacco Substitutes",
    "25": "Salt; Sulfur; Earths and Stone; Plastering Materials, Lime and Cement",
    "26": "Ores, Slag and Ash",
    "27": "Mineral Fuels, Mineral Oils and Products of Their Distillation; Bituminous Substances; Mineral Waxes",
    "28": "Inorganic Chemicals; Organic or Inorganic Compounds of Precious Metals, of Rare-Earth Metals, of Radioactive Elements or of Isotopes",
    "29": "Organic Chemicals",
    "30": "Pharmaceutical Products",
    "31": "Fertilizers",
    "32": "Tanning or Dyeing Extracts; Tannins and Their Derivatives; Dyes, Pigments and Other Coloring Matter; Paints and Varnishes; Putty and Other Mastics; Inks",
    "33": "Essential Oils and Resinoids; Perfumery, Cosmetic or Toilet Preparations",
    "34": "Soap, Organic Surface-Active Agents, Washing Preparations, Lubricating Preparations, Artificial Waxes, Prepared Waxes, Polishing or Scouring Preparations, Candles and Similar Articles, Modeling Pastes, \"Dental Waxes\" and Dental Preparations with a Basis of Plaster",
    "35": "Albuminoidal Substances; Modified Starches; Glues; Enzymes",
    "36": "Explosives; Pyrotechnic Products; Matches; Pyrophoric Alloys; Certain Combustible Preparations",
    "37": "Photographic or Cinematographic Goods",
    "38": "Miscellaneous Chemical Products",
    "39": "Plastics and Articles Thereof",
    "40": "Rubber and Articles Thereof",
    "41": "Raw Hides and Skins (Other Than Furskins) and Leather",
    "42": "Articles of Leather; Saddlery and Harness; Travel Goods, Handbags and Similar Containers; Articles of Animal Gut (Other Than Silkworm Gut)",
    "43": "Furskins and Artificial Fur; Manufactures Thereof",
    "44": "Wood and Articles of Wood; Wood Charcoal",
    "45": "Cork and Articles of Cork",
    "46": "Manufactures of Straw, of Esparto or of Other Plaiting Materials; Basketware and Wickerwork",
    "47": "Pulp of Wood or of Other Fibrous Cellulosic Material; Recovered (Waste and Scrap) Paper or Paperboard",
    "48": "Paper and Paperboard; Articles of Paper Pulp, of Paper or of Paperboard",
    "49": "Printed Books, Newspapers, Pictures and Other Products of the Printing Industry; Manuscripts, Typescripts and Plans",
    "50": "Silk",
    "51": "Wool, Fine or Coarse Animal Hair; Horsehair Yarn and Woven Fabric",
    "52": "Cotton",
    "53": "Other Vegetable Textile Fibers; Paper Yarn and Woven Fabrics of Paper Yarn",
    "54": "Man-Made Filaments; Strip and the Like of Man-Made Textile Materials",
    "55": "Man-Made Staple Fibers",
    "56": "Wadding, Felt and Nonwovens; Special Yarns; Twine, Cordage, Ropes and Cables and Articles Thereof",
    "57": "Carpets and Other Textile Floor Coverings",
    "58": "Special Woven Fabrics; Tufted Textile Fabrics; Lace; Tapestries; Trimmings; Embroidery",
    "59": "Impregnated, Coated, Covered or Laminated Textile Fabrics; Textile Articles of a Kind Suitable for Industrial Use",
    "60": "Knitted or Crocheted Fabrics",
    "61": "Articles of Apparel and Clothing Accessories, Knitted or Crocheted",
    "62": "Articles of Apparel and Clothing Accessories, Not Knitted or Crocheted",
    "63": "Other Made Up Textile Articles; Sets; Worn Clothing and Worn Textile Articles; Rags",
    "64": "Footwear, Gaiters and the Like; Parts of Such Articles",
    "65": "Headgear and Parts Thereof",
    "66": "Umbrellas, Sun Umbrellas, Walking Sticks, Seat-Sticks, Whips, Riding-Crops and Parts Thereof",
    "67": "Prepared Feathers and Down and Articles Made of Feathers or of Down; Artificial Flowers; Articles of Human Hair",
    "68": "Articles of Stone, Plaster, Cement, Asbestos, Mica or Similar Materials",
    "69": "Ceramic Products",
    "70": "Glass and Glassware",
    "71": "Natural or Cultured Pearls, Precious or Semiprecious Stones, Precious Metals, Metals Clad with Precious Metal, and Articles Thereof; Imitation Jewelry; Coin",
    "72": "Iron and Steel",
    "73": "Articles of Iron or Steel",
    "74": "Copper and Articles Thereof",
    "75": "Nickel and Articles Thereof",
    "76": "Aluminum and Articles Thereof",
    "77": "Reserved for Possible Future Use",
    "78": "Lead and Articles Thereof",
    "79": "Zinc and Articles Thereof",
    "80": "Tin and Articles Thereof",
    "81": "Other Base Metals; Cermets; Articles Thereof",
    "82": "Tools, Implements, Cutlery, Spoons and Forks, of Base Metal; Parts Thereof of Base Metal",
    "83": "Miscellaneous Articles of Base Metal",
    "84": "Nuclear Reactors, Boilers, Machinery and Mechanical Appliances; Parts Thereof",
    "85": "Electrical Machinery and Equipment and Parts Thereof; Sound Recorders and Reproducers, Television Image and Sound Recorders and Reproducers, and Parts and Accessories of Such Articles",
    "86": "Railway or Tramway Locomotives, Rolling Stock and Parts Thereof; Railway or Tramway Track Fixtures and Fittings and Parts Thereof; Mechanical (Including Electromechanical) Traffic Signaling Equipment of All Kinds",
    "87": "Vehicles Other Than Railway or Tramway Rolling Stock, and Parts and Accessories Thereof",
    "88": "Aircraft, Spacecraft, and Parts Thereof",
    "89": "Ships, Boats and Floating Structures",
    "90": "Optical, Photographic, Cinematographic, Measuring, Checking, Precision, Medical or Surgical Instruments and Apparatus; Parts and Accessories Thereof",
    "91": "Clocks and Watches and Parts Thereof",
    "92": "Musical Instruments; Parts and Accessories of Such Articles",
    "93": "Arms and Ammunition; Parts and Accessories Thereof",
    "94": "Furniture; Bedding, Mattresses, Mattress Supports, Cushions and Similar Stuffed Furnishings; Lamps and Lighting Fittings, Not Elsewhere Specified or Included; Illuminated Signs, Illuminated Nameplates and the Like; Prefabricated Buildings",
    "95": "Toys, Games and Sports Requisites; Parts and Accessories Thereof",
    "96": "Miscellaneous Manufactured Articles",
    "97": "Works of Art, Collectors' Pieces and Antiques",
    "98": "Special Classification Provisions",
    "99": "Temporary Legislation; Temporary Modifications Proclaimed Pursuant to Trade Agreements Legislation; Additional Import Restrictions Proclaimed Pursuant to Section 22 of the Agricultural Adjustment Act, as Amended",
}


def update_chapter_titles(db_path: str = "data/hts.db"):
    """Update chapter descriptions with real HTS titles. Safe to re-run."""
    db = sqlite3.connect(db_path)
    try:
        for number, title in HTS_CHAPTER_TITLES.items():
            db.execute(
                "UPDATE chapters SET description = ? WHERE number = ?",
                (title, number),
            )
        db.commit()
        print(f"Updated {len(HTS_CHAPTER_TITLES)} chapter titles in {db_path}")
    finally:
        db.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/hts.db"
    update_chapter_titles(path)
