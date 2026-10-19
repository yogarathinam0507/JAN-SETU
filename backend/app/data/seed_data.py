"""Deterministic demo configuration. Department names and helpline numbers are starting points that MUST be
verified against official lists before any public deployment (name_verified=False everywhere)."""

# category code -> (department code, default priority, family, names, requires_photo_verification)
CATEGORIES = {
    "streetlight": ("STREETLIGHT", "Medium", "Electrical / street lighting",
                    {"en": "Streetlight not working", "hi": "स्ट्रीट लाइट खराब", "kn": "ಬೀದಿ ದೀಪ ಕೆಟ್ಟಿದೆ", "ta": "தெரு விளக்கு பழுது"}, True),
    "power_hazard": ("ELEC_EMG", "Emergency", "Electricity utility rapid response",
                     {"en": "Electrical hazard (sparking / live wire)", "hi": "बिजली खतरा (चिंगारी / खुला तार)",
                      "kn": "ವಿದ್ಯುತ್ ಅಪಾಯ (ಕಿಡಿ / ತೆರೆದ ತಂತಿ)", "ta": "மின் அபாயம் (தீப்பொறி / மின்கம்பி)"}, True),
    "power_outage": ("ELEC", "High", "Electricity supply",
                     {"en": "Power outage / voltage problem", "hi": "बिजली कटौती", "kn": "ವಿದ್ಯುತ್ ಕಡಿತ", "ta": "மின்வெட்டு"}, False),
    "water_quality": ("WATER", "High", "Water supply & sewerage",
                      {"en": "Contaminated / dirty water", "hi": "गंदा / दूषित पानी", "kn": "ಕಲುಷಿತ ನೀರು", "ta": "அசுத்தமான குடிநீர்"}, False),
    "water_supply": ("WATER", "High", "Water supply & sewerage",
                     {"en": "No water / supply problem", "hi": "पानी की आपूर्ति नहीं", "kn": "ನೀರು ಪೂರೈಕೆ ಸಮಸ್ಯೆ", "ta": "குடிநீர் விநியோக பிரச்சினை"}, False),
    "sewage": ("WATER", "High", "Water supply & sewerage",
               {"en": "Sewage overflow / manhole", "hi": "सीवर ओवरफ्लो", "kn": "ಒಳಚರಂಡಿ ಉಕ್ಕಿ ಹರಿಯುತ್ತಿದೆ", "ta": "கழிவுநீர் வழிதல்"}, True),
    "garbage": ("SWM", "Medium", "Solid waste management",
                {"en": "Garbage not collected", "hi": "कचरा नहीं उठाया गया", "kn": "ಕಸ ಸಂಗ್ರಹಿಸಿಲ್ಲ", "ta": "குப்பை அள்ளப்படவில்லை"}, True),
    "roads": ("ROADS", "Medium", "Roads / public works",
              {"en": "Pothole / damaged road", "hi": "गड्ढा / टूटी सड़क", "kn": "ರಸ್ತೆ ಗುಂಡಿ", "ta": "சாலை பள்ளம்"}, True),
    "mosquito": ("HEALTH", "Medium", "Public health / vector control",
                 {"en": "Mosquito breeding / fogging", "hi": "मच्छर / फॉगिंग", "kn": "ಸೊಳ್ಳೆ ಉತ್ಪತ್ತಿ", "ta": "கொசு உற்பத்தி"}, False),
    "stray_animals": ("VET", "High", "Veterinary / animal control",
                      {"en": "Stray animal menace", "hi": "आवारा पशु", "kn": "ಬೀದಿ ಪ್ರಾಣಿಗಳ ಹಾವಳಿ", "ta": "தெரு விலங்கு தொல்லை"}, False),
    "storm_drain": ("SWD", "High", "Storm water drains / flooding",
                    {"en": "Waterlogging / blocked storm drain", "hi": "जलभराव", "kn": "ನೀರು ನಿಲ್ಲುವಿಕೆ / ರಾಜಕಾಲುವೆ", "ta": "மழைநீர் தேக்கம்"}, True),
    "fallen_tree": ("PARKS", "High", "Parks & trees",
                    {"en": "Fallen tree / branch", "hi": "पेड़ गिरा", "kn": "ಮರ ಬಿದ್ದಿದೆ", "ta": "மரம் விழுந்தது"}, True),
    "fire": ("FIRE", "Emergency", "Fire & emergency services (referral)",
             {"en": "Fire / gas leak", "hi": "आग / गैस रिसाव", "kn": "ಬೆಂಕಿ / ಅನಿಲ ಸೋರಿಕೆ", "ta": "தீ / எரிவாயு கசிவு"}, False),
    "public_toilet": ("SWM", "Medium", "Sanitation",
                      {"en": "Public toilet problem", "hi": "सार्वजनिक शौचालय", "kn": "ಸಾರ್ವಜನಿಕ ಶೌಚಾಲಯ", "ta": "பொது கழிப்பறை"}, False),
    "property_tax": ("REVENUE", "Low", "Revenue / property tax",
                     {"en": "Property tax / khata issue", "hi": "संपत्ति कर", "kn": "ಆಸ್ತಿ ತೆರಿಗೆ / ಖಾತಾ", "ta": "சொத்து வரி"}, False),
    "ration": ("FOOD", "Medium", "Food & civil supplies",
               {"en": "Ration / PDS issue", "hi": "राशन समस्या", "kn": "ಪಡಿತರ ಸಮಸ್ಯೆ", "ta": "ரேஷன் பிரச்சினை"}, False),
    "pension": ("WELFARE", "Medium", "Social welfare & pensions",
                {"en": "Pension not received", "hi": "पेंशन नहीं मिली", "kn": "ಪಿಂಚಣಿ ಬಂದಿಲ್ಲ", "ta": "ஓய்வூதியம் வரவில்லை"}, False),
    "power_billing": ("ELEC", "Low", "Electricity billing & connections",
                      {"en": "Electricity bill / meter / connection", "hi": "बिजली बिल / मीटर", "kn": "ವಿದ್ಯುತ್ ಬಿಲ್ / ಮೀಟರ್", "ta": "மின் கட்டணம் / மீட்டர்"}, False),
    "encroachment": ("TOWN_PLANNING", "Medium", "Town planning & enforcement",
                     {"en": "Encroachment / illegal construction", "hi": "अतिक्रमण / अवैध निर्माण", "kn": "ಒತ್ತುವರಿ / ಅಕ್ರಮ ಕಟ್ಟಡ", "ta": "ஆக்கிரமிப்பு / சட்டவிரோத கட்டிடம்"}, True),
    "noise": ("POLLUTION", "Medium", "Pollution control",
              {"en": "Noise pollution", "hi": "ध्वनि प्रदूषण", "kn": "ಶಬ್ದ ಮಾಲಿನ್ಯ", "ta": "ஒலி மாசு"}, False),
    "dead_animal": ("SWM", "High", "Solid waste management",
                    {"en": "Dead animal removal", "hi": "मृत पशु हटाना", "kn": "ಸತ್ತ ಪ್ರಾಣಿ ತೆರವು", "ta": "இறந்த விலங்கு அகற்றல்"}, True),
    "bus": ("TRANSPORT", "Low", "Public transport",
            {"en": "Bus service issue", "hi": "बस सेवा", "kn": "ಬಸ್ ಸೇವೆ", "ta": "பேருந்து சேவை"}, False),
}

TENANTS = [
    {
        "code": "ka-bengaluru", "name": "Karnataka - Bengaluru", "state": "Karnataka",
        "default_language": "kn", "languages": ["kn", "en", "hi", "ta"],
        "branding": {"title": "JanSetu Karnataka", "subtitle": "Integrated Citizen Grievance Redressal & Services Portal",
                     "region": "Bengaluru", "helpline": "1902", "accent": "#0b3d91"},
        "emergency_contacts": [{"label": "Emergency (ERSS)", "number": "112"}, {"label": "Fire", "number": "101"},
                               {"label": "Ambulance", "number": "108"}],
        "departments": {
            "ELEC": ({"en": "BESCOM - Electricity Supply", "kn": "ಬೆಸ್ಕಾಂ - ವಿದ್ಯುತ್ ಸರಬರಾಜು", "hi": "बेस्कॉम - बिजली आपूर्ति"}, "Energy Department", {"helpline": "1912"}),
            "ELEC_EMG": ({"en": "BESCOM Rapid Response - Electrical Hazards", "kn": "ಬೆಸ್ಕಾಂ ತುರ್ತು ಸ್ಪಂದನೆ", "hi": "बेस्कॉम आपातकालीन प्रतिक्रिया"}, "Energy Department", {"helpline": "1912"}),
            "STREETLIGHT": ({"en": "Street Lighting Division", "kn": "ಬೀದಿ ದೀಪ ವಿಭಾಗ", "hi": "स्ट्रीट लाइटिंग विभाग"}, "Bengaluru civic body", {}),
            "WATER": ({"en": "BWSSB - Water Supply & Sewerage", "kn": "ಜಲಮಂಡಳಿ - ನೀರು ಸರಬರಾಜು ಮತ್ತು ಒಳಚರಂಡಿ", "hi": "जल आपूर्ति और सीवरेज बोर्ड"}, "BWSSB", {"helpline": "1916"}),
            "SWM": ({"en": "Solid Waste Management", "kn": "ಘನತ್ಯಾಜ್ಯ ನಿರ್ವಹಣೆ", "hi": "ठोस अपशिष्ट प्रबंधन"}, "Bengaluru civic body", {}),
            "ROADS": ({"en": "Roads & Infrastructure", "kn": "ರಸ್ತೆ ಮತ್ತು ಮೂಲಸೌಕರ್ಯ", "hi": "सड़क और अवसंरचना"}, "Bengaluru civic body", {}),
            "HEALTH": ({"en": "Public Health & Vector Control", "kn": "ಸಾರ್ವಜನಿಕ ಆರೋಗ್ಯ", "hi": "जन स्वास्थ्य"}, "Bengaluru civic body", {}),
            "VET": ({"en": "Animal Husbandry & Veterinary Services", "kn": "ಪಶುಸಂಗೋಪನೆ ಮತ್ತು ಪಶುವೈದ್ಯ ಸೇವೆ", "hi": "पशुपालन एवं पशु चिकित्सा"}, "Bengaluru civic body", {}),
            "SWD": ({"en": "Storm Water Drains", "kn": "ರಾಜಕಾಲುವೆ ವಿಭಾಗ", "hi": "वर्षा जल निकासी"}, "Bengaluru civic body", {}),
            "PARKS": ({"en": "Forest, Parks & Trees", "kn": "ಅರಣ್ಯ ಮತ್ತು ಉದ್ಯಾನವನ", "hi": "वन, उद्यान और वृक्ष"}, "Bengaluru civic body", {}),
            "FIRE": ({"en": "Fire & Emergency Services", "kn": "ಅಗ್ನಿಶಾಮಕ ಮತ್ತು ತುರ್ತು ಸೇವೆಗಳು", "hi": "अग्निशमन एवं आपात सेवाएँ"}, "Karnataka Fire & Emergency Services", {"emergency": "101 / 112"}),
            "REVENUE": ({"en": "Revenue & Property Tax", "kn": "ಕಂದಾಯ ಮತ್ತು ಆಸ್ತಿ ತೆರಿಗೆ", "hi": "राजस्व एवं संपत्ति कर"}, "Revenue Department", {}),
            "FOOD": ({"en": "Food & Civil Supplies", "kn": "ಆಹಾರ ಮತ್ತು ನಾಗರಿಕ ಸರಬರಾಜು", "hi": "खाद्य एवं नागरिक आपूर्ति"}, "Food, Civil Supplies & Consumer Affairs", {}),
            "WELFARE": ({"en": "Social Welfare & Pensions", "kn": "ಸಮಾಜ ಕಲ್ಯಾಣ ಮತ್ತು ಪಿಂಚಣಿ", "hi": "समाज कल्याण एवं पेंशन"}, "Social Welfare Department", {}),
            "TRANSPORT": ({"en": "BMTC - Public Transport", "kn": "ಬಿಎಂಟಿಸಿ - ಸಾರ್ವಜನಿಕ ಸಾರಿಗೆ", "hi": "बीएमटीसी - सार्वजनिक परिवहन"}, "Transport Department", {}),
            "TOWN_PLANNING": ({"en": "Town Planning & Enforcement", "kn": "ನಗರ ಯೋಜನೆ ಮತ್ತು ಜಾರಿ", "hi": "नगर नियोजन एवं प्रवर्तन"}, "Bengaluru civic body", {}),
            "POLLUTION": ({"en": "Pollution Control (Noise & Air)", "kn": "ಮಾಲಿನ್ಯ ನಿಯಂತ್ರಣ", "hi": "प्रदूषण नियंत्रण"}, "State Pollution Control Board", {}),
        },
        "zones": {"SOUTH": ("South Zone", [("JAYANAGAR", "Jayanagar", (12.925, 77.583), ["jayanagar 4th block", "jayanagara", "ಜಯನಗರ"]),
                                           ("KORAMANGALA", "Koramangala", (12.935, 77.624), ["ಕೋರಮಂಗಲ"]),
                                           ("BTM", "BTM Layout", (12.9166, 77.6101), ["btm", "ಬಿಟಿಎಂ"]),
                                           ("HSR", "HSR Layout", (12.9121, 77.6446), ["hsr", "ಎಚ್ಎಸ್ಆರ್"])]),
                  "EAST": ("East Zone", [("INDIRANAGAR", "Indiranagar", (12.978, 77.640), ["indira nagar", "hal 2nd stage", "ಇಂದಿರಾನಗರ"]),
                                         ("WHITEFIELD", "Whitefield", (12.970, 77.750), ["ವೈಟ್‌ಫೀಲ್ಡ್"]),
                                         ("MARATHAHALLI", "Marathahalli", (12.9591, 77.6974), ["ಮಾರತ್ತಹಳ್ಳಿ"])]),
                  "WEST": ("West Zone", [("MALLESHWARAM", "Malleshwaram", (13.003, 77.570), ["malleswaram", "ಮಲ್ಲೇಶ್ವರ"]),
                                         ("RAJAJINAGAR", "Rajajinagar", (12.9850, 77.5480), ["ರಾಜಾಜಿನಗರ"])]),
                  "NORTH": ("North Zone", [("HEBBAL", "Hebbal", (13.0358, 77.5970), ["ಹೆಬ್ಬಾಳ"]),
                                           ("YELAHANKA", "Yelahanka", (13.1005, 77.5963), ["ಯಲಹಂಕ"])])},
        "prefix": "ka",
        "people": {
            "citizen1": ("Lakshmi Narayan", ""), "citizen2": ("Ravi Shankar", ""),
            "agent1": ("Divya N.", "Helpline Executive"), "agent2": ("Kiran S.", "Helpline Executive"),
            "nodal": ("Smt. Kavitha Rao", "Joint Commissioner (Nodal Officer)"), "nodal.south": ("Sri. Arun Prasad", "Nodal Officer, South Zone"),
            "hod": ("Sri. Vinod Krishnan", "Commissioner"), "vendor": ("Sri. Ganesh M.", "Site Supervisor, Sri Sai Infra Works"),
            "auditor": ("Sri. Ramesh Iyer", "Internal Audit Officer"), "content": ("Ms. Pooja Bhat", "Content & Language Officer"),
            "admin": ("Sri. Sandeep Rao", "System Administrator"),
        },
        "officers": {
            "ELEC": ("Sri. Manjunath Gowda", "Assistant Executive Engineer (Electrical)"),
            "ELEC_EMG": ("Sri. Prakash Hegde", "Executive Engineer, Rapid Response"),
            "STREETLIGHT": ("Sri. Raghavendra Rao", "Assistant Engineer (Street Lighting)"),
            "WATER": ("Smt. Kavya Shetty", "Assistant Executive Engineer (Water Supply)"),
            "SWM": ("Sri. Mohammed Irfan", "Senior Health Inspector (Solid Waste)"),
            "ROADS": ("Sri. Suresh Kumar B.", "Assistant Executive Engineer (Roads)"),
            "HEALTH": ("Dr. Anitha Murthy", "Medical Officer of Health"),
            "VET": ("Dr. Venkatesh Naik", "Veterinary Officer"),
            "SWD": ("Sri. Nagaraj Patil", "Assistant Engineer (Storm Water Drains)"),
            "PARKS": ("Smt. Shobha Kulkarni", "Range Forest Officer (Urban Trees)"),
            "FIRE": ("Sri. Harish Reddy", "Station Fire Officer"),
            "REVENUE": ("Sri. Mahesh Joshi", "Assistant Revenue Officer"),
            "FOOD": ("Smt. Lakshmi Devi", "Food Inspector"),
            "WELFARE": ("Sri. Basavaraj Hiremath", "Social Welfare Officer"),
            "TRANSPORT": ("Sri. Imran Pasha", "Depot Manager"),
            "TOWN_PLANNING": ("Sri. Chetan Kumar", "Assistant Director (Town Planning)"),
            "POLLUTION": ("Smt. Rekha Prasad", "Environmental Officer"),
        },
        "vendor_name": "Sri Sai Infra Works",
        "landmarks": ["bus stop", "temple", "government school", "park", "market", "metro station", "post office", "community hall",
                      "1st Main Road", "4th Cross", "9th Main", "100 Feet Road", "BDA complex", "water tank", "primary health centre"],
    },
    {
        "code": "tn-chennai", "name": "Tamil Nadu - Greater Chennai", "state": "Tamil Nadu",
        "default_language": "ta", "languages": ["ta", "en", "hi", "kn"],
        "branding": {"title": "JanSetu Tamil Nadu", "subtitle": "Integrated Citizen Grievance Redressal & Services Portal",
                     "region": "Greater Chennai", "helpline": "1913", "accent": "#0b3d91"},
        "emergency_contacts": [{"label": "Emergency (ERSS)", "number": "112"}, {"label": "Fire", "number": "101"},
                               {"label": "Ambulance", "number": "108"}],
        "departments": {
            "ELEC": ({"en": "TNPDCL - Electricity Distribution", "ta": "மின் விநியோகம்", "hi": "बिजली वितरण"}, "Energy Department", {}),
            "ELEC_EMG": ({"en": "Electricity Rapid Response", "ta": "மின் அவசர சேவை", "hi": "बिजली आपातकालीन सेवा"}, "Energy Department", {}),
            "STREETLIGHT": ({"en": "Electrical Department - Street Lighting", "ta": "தெரு விளக்கு பிரிவு", "hi": "स्ट्रीट लाइटिंग"}, "Greater Chennai Corporation", {"helpline": "1913"}),
            "WATER": ({"en": "Metro Water & Sewerage Board", "ta": "குடிநீர் மற்றும் கழிவுநீர் வாரியம்", "hi": "मेट्रो जल एवं सीवरेज बोर्ड"}, "Chennai Metro Water", {}),
            "SWM": ({"en": "Solid Waste Management", "ta": "திடக்கழிவு மேலாண்மை", "hi": "ठोस अपशिष्ट प्रबंधन"}, "Greater Chennai Corporation", {"helpline": "1913"}),
            "ROADS": ({"en": "Roads & Bus Route Roads", "ta": "சாலைகள் துறை", "hi": "सड़क विभाग"}, "Greater Chennai Corporation", {}),
            "HEALTH": ({"en": "Public Health & Vector Control", "ta": "பொது சுகாதாரம்", "hi": "जन स्वास्थ्य"}, "Greater Chennai Corporation", {}),
            "VET": ({"en": "Veterinary Public Health", "ta": "கால்நடை பொது சுகாதாரம்", "hi": "पशु चिकित्सा जन स्वास्थ्य"}, "Greater Chennai Corporation", {}),
            "SWD": ({"en": "Storm Water Drains", "ta": "மழைநீர் வடிகால்", "hi": "वर्षा जल निकासी"}, "Greater Chennai Corporation", {}),
            "PARKS": ({"en": "Parks & Trees", "ta": "பூங்காக்கள் மற்றும் மரங்கள்", "hi": "उद्यान एवं वृक्ष"}, "Greater Chennai Corporation", {}),
            "FIRE": ({"en": "Fire & Rescue Services", "ta": "தீயணைப்பு மற்றும் மீட்பு பணிகள்", "hi": "अग्निशमन एवं बचाव"}, "TN Fire & Rescue Services", {"emergency": "101 / 112"}),
            "REVENUE": ({"en": "Revenue & Property Tax", "ta": "வருவாய் மற்றும் சொத்து வரி", "hi": "राजस्व एवं संपत्ति कर"}, "Greater Chennai Corporation", {}),
            "FOOD": ({"en": "Civil Supplies & Ration", "ta": "குடிமைப் பொருள் வழங்கல்", "hi": "नागरिक आपूर्ति"}, "Civil Supplies Department", {}),
            "WELFARE": ({"en": "Social Welfare & Pensions", "ta": "சமூக நலன் மற்றும் ஓய்வூதியம்", "hi": "समाज कल्याण एवं पेंशन"}, "Social Welfare Department", {}),
            "TRANSPORT": ({"en": "Metropolitan Transport (City Bus)", "ta": "மாநகர போக்குவரத்து", "hi": "सार्वजनिक परिवहन"}, "Transport Department", {}),
            "TOWN_PLANNING": ({"en": "Town Planning & Enforcement", "ta": "நகரமைப்பு மற்றும் அமலாக்கம்", "hi": "नगर नियोजन एवं प्रवर्तन"}, "Greater Chennai Corporation", {}),
            "POLLUTION": ({"en": "Pollution Control (Noise & Air)", "ta": "மாசு கட்டுப்பாடு", "hi": "प्रदूषण नियंत्रण"}, "State Pollution Control Board", {}),
        },
        "zones": {"NORTH": ("North Zone", [("ANNANAGAR", "Anna Nagar", (13.085, 80.210), ["annanagar", "anna nagar west", "அண்ணா நகர்"]),
                                           ("PERAMBUR", "Perambur", (13.115, 80.233), ["பெரம்பூர்"]),
                                           ("ROYAPURAM", "Royapuram", (13.1137, 80.2954), ["ராயபுரம்"])]),
                  "CENTRAL": ("Central Zone", [("TNAGAR", "T. Nagar", (13.042, 80.234), ["t nagar", "thyagaraya nagar", "தி. நகர்", "தியாகராய நகர்"]),
                                               ("MYLAPORE", "Mylapore", (13.034, 80.268), ["மயிலாப்பூர்"])]),
                  "SOUTH": ("South Zone", [("ADYAR", "Adyar", (13.006, 80.257), ["அடையாறு", "அடையார்"]),
                                           ("VELACHERY", "Velachery", (12.979, 80.218), ["வேளச்சேரி"]),
                                           ("GUINDY", "Guindy", (13.0067, 80.2206), ["கிண்டி"]),
                                           ("TAMBARAM", "Tambaram", (12.9249, 80.1000), ["தாம்பரம்"])])},
        "prefix": "tn",
        "people": {
            "citizen1": ("Meena Sundaram", ""), "citizen2": ("Arun Kumar", ""),
            "agent1": ("Priya R.", "Helpline Executive"), "agent2": ("Arun K.", "Helpline Executive"),
            "nodal": ("Tmt. S. Anitha", "Deputy Commissioner (Nodal Officer)"), "nodal.south": ("Thiru. R. Ganesan", "Nodal Officer, South Zone"),
            "hod": ("Thiru. K. Venkatesan", "Commissioner"), "vendor": ("Thiru. P. Selvam", "Site Supervisor, Sri Murugan Constructions"),
            "auditor": ("Thiru. L. Narayanan", "Internal Audit Officer"), "content": ("Ms. Deepa S.", "Content & Language Officer"),
            "admin": ("Thiru. B. Suresh", "System Administrator"),
        },
        "officers": {
            "ELEC": ("Thiru. S. Senthil Kumar", "Assistant Engineer (Distribution)"),
            "ELEC_EMG": ("Thiru. R. Murugan", "Executive Engineer, Rapid Response"),
            "STREETLIGHT": ("Thiru. K. Rajesh", "Assistant Engineer (Street Lighting)"),
            "WATER": ("Tmt. P. Meenakshi", "Area Engineer (Water Supply)"),
            "SWM": ("Thiru. A. Abdul Rahman", "Sanitary Officer"),
            "ROADS": ("Thiru. V. Karthik", "Assistant Engineer (Roads)"),
            "HEALTH": ("Dr. S. Revathi", "Zonal Health Officer"),
            "VET": ("Dr. M. Balaji", "Veterinary Assistant Surgeon"),
            "SWD": ("Thiru. G. Prabhu", "Assistant Engineer (Storm Water Drains)"),
            "PARKS": ("Tmt. R. Kalaivani", "Parks Superintendent"),
            "FIRE": ("Thiru. N. Saravanan", "Station Officer"),
            "REVENUE": ("Thiru. T. Ramesh", "Assistant Revenue Officer"),
            "FOOD": ("Tmt. J. Vasanthi", "Assistant Commissioner (Civil Supplies)"),
            "WELFARE": ("Thiru. D. Elango", "Social Welfare Officer"),
            "TRANSPORT": ("Thiru. M. Raja", "Depot Manager"),
            "TOWN_PLANNING": ("Thiru. S. Vijay", "Assistant Executive Engineer (Town Planning)"),
            "POLLUTION": ("Tmt. K. Jayanthi", "Assistant Environmental Engineer"),
        },
        "vendor_name": "Sri Murugan Constructions",
        "landmarks": ["bus stand", "temple", "corporation school", "park", "market", "metro station", "post office", "kalyana mandapam",
                      "1st Avenue", "2nd Street", "Main Road", "100 Feet Road", "anganwadi centre", "overhead tank", "urban health centre"],
    },
]

# Synthetic complaint templates (English) per category, used to generate realistic, correctly-located test data.
TEMPLATES_BY_CATEGORY = {
    "streetlight": ["Streetlight not working near the {lm} for {d} days", "Street lights are not working on {lm}, area is very dark",
                    "No street light near the {lm}, women feel unsafe at night"],
    "power_hazard": ["Transformer sparking near the {lm}", "Live wire hanging low near the {lm}", "Electric pole is leaning near the {lm} and may fall"],
    "power_outage": ["Power cut since morning near the {lm}", "Frequent power cuts in our area near the {lm}", "Voltage fluctuation near the {lm}, appliances damaged"],
    "power_billing": ["Electricity bill is very high this month, meter reading wrong", "Meter is faulty at my house near the {lm}"],
    "water_quality": ["Dirty water from the tap near the {lm}", "Water is coming with mud near the {lm}", "Contaminated drinking water supply near the {lm}"],
    "water_supply": ["No water supply for {d} days near the {lm}", "Water pipeline burst near the {lm}, water wasting", "Low water pressure near the {lm}"],
    "sewage": ["Drainage is blocked and smelling near the {lm}", "Sewage overflowing from manhole near the {lm}", "Open drain overflowing in front of the {lm}"],
    "garbage": ["Garbage not collected for a week near the {lm}", "Garbage dumped on the road near the {lm}", "Overflowing dustbin near the {lm}"],
    "roads": ["Large pothole on the road near the {lm}", "Road is very bad and full of holes near the {lm}", "Road digging work left incomplete near the {lm}"],
    "mosquito": ["Mosquito breeding in stagnant water near the {lm}", "Dengue cases rising near the {lm}, please do fogging"],
    "stray_animals": ["Stray dogs attacking people near the {lm}", "Stray cattle on the road near the {lm} causing accidents"],
    "storm_drain": ["Severe waterlogging near the {lm} after rain", "Storm water drain blocked near the {lm}, road flooded"],
    "fallen_tree": ["A big tree has fallen on the road near the {lm}", "Branches need trimming near the {lm}"],
    "fire": ["Fire in the garbage dump near the {lm}"],
    "encroachment": ["Illegal construction next to the {lm}", "Footpath occupied by shops near the {lm}"],
    "noise": ["Loud music at night near the {lm}", "Loudspeakers used late night near the {lm}"],
    "dead_animal": ["Dead dog lying on the road near the {lm}"],
    "public_toilet": ["Public toilet near the {lm} is locked and dirty"],
    "property_tax": ["My property tax receipt is not generated"],
    "ration": ["Ration shop near the {lm} did not give rice this month"],
    "pension": ["Old age pension not received for three months"],
    "bus": ["Bus not stopping at the {lm} bus stop"],
}
# weights: how often each category appears in synthetic data
CATEGORY_MIX = {"streetlight": 7, "water_supply": 7, "garbage": 8, "roads": 8, "sewage": 6, "water_quality": 4, "power_outage": 5,
                "power_hazard": 3, "mosquito": 4, "stray_animals": 4, "storm_drain": 4, "fallen_tree": 3, "encroachment": 3, "noise": 2,
                "dead_animal": 2, "power_billing": 2, "public_toilet": 1, "fire": 1, "bus": 1, "ration": 1, "pension": 1, "property_tax": 1}
SYNTHETIC_PER_TENANT = 90
# final-status distribution for synthetic tickets
STATUS_MIX = {"submitted": 22, "accepted": 15, "in_progress": 18, "resolved": 12, "closed": 25, "rejected": 3, "reopened": 5}

SLA = [("Emergency", 1, 4, "Life/property risk - immediate response"), ("High", 4, 24, "Health/safety impact"),
       ("Medium", 24, 72, "Civic service failure"), ("Low", 48, 168, "Administrative / informational")]
ESCALATION = [(1, "nodal", 1.0, "Escalate to the ward/zone nodal officer when the SLA is breached"),
              (2, "hod", 1.5, "Escalate to head of department at 1.5x SLA")]

# A few hand-written multilingual complaints added on top of the synthetic ones (language coverage).
EXTRA_GRIEVANCES = {
    "ka-bengaluru": [("ಜಯನಗರದಲ್ಲಿ ಬೀದಿ ದೀಪ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ", "kn", "JAYANAGAR"), ("ನಲ್ಲಿಯಲ್ಲಿ ಕಲುಷಿತ ನೀರು ಬರುತ್ತಿದೆ, ಇಂದಿರಾನಗರ", "kn", "INDIRANAGAR"),
                     ("ಒಂದು ವಾರದಿಂದ ಕಸ ಸಂಗ್ರಹಿಸಿಲ್ಲ, ಮಲ್ಲೇಶ್ವರ", "kn", "MALLESHWARAM"), ("ಎರಡು ದಿನದಿಂದ ಕರೆಂಟ್ ಇಲ್ಲ", "kn", "HEBBAL"),
                     ("सड़क पर बड़ा गड्ढा है", "hi", "WHITEFIELD"), ("asdkj qwe zzkx plmnb", "en", None)],
    "tn-chennai": [("எங்கள் தெருவில் தெரு விளக்கு மூன்று நாட்களாக எரியவில்லை, அண்ணா நகர்", "ta", "ANNANAGAR"),
                   ("குழாயில் அழுக்கு தண்ணீர் வருகிறது மயிலாப்பூர்", "ta", "MYLAPORE"), ("ஒரு வாரமாக குப்பை அள்ளப்படவில்லை", "ta", "ADYAR"),
                   ("नल से गंदा पानी आ रहा है", "hi", "TNAGAR"), ("What is the cricket score today", "en", None)],
}

KB_DOCS = {
    "ka-bengaluru": [
        ("grievance-procedure", "How grievance redressal works on this platform", "", "en", True, False, "Platform documentation",
         "Every complaint receives a ticket ID immediately after you confirm it. The complaint is classified by category and "
         "routed to the responsible department. If the system is not confident about the category, a nodal officer reviews it "
         "manually - the complaint is never assigned arbitrarily.\n\nYou can track your ticket with its ID on the Track page. "
         "When the department resolves the issue you are asked to confirm. If you are not satisfied you can reject the closure "
         "with a reason, and the ticket is reopened.\n\nIf a ticket is not resolved within the service-level time for its "
         "priority, it is escalated automatically: first to the zone nodal officer, then to the head of department."),
        ("sla-policy", "Service-level timelines configured on this platform", "", "en", True, False, "Platform configuration (SLA table)",
         "Emergency complaints: first response within 1 hour, resolution target 4 hours. High priority: first response 4 hours, "
         "resolution 24 hours. Medium priority: first response 24 hours, resolution 72 hours. Low priority: first response "
         "48 hours, resolution 7 days.\n\nThese timelines are the demo configuration of this platform. The deploying authority "
         "sets the official values in the admin console."),
        ("gruha-lakshmi-summary", "Gruha Lakshmi - scheme summary (sample)", "WELFARE", "en", False, True, "",
         "Gruha Lakshmi is a Karnataka government scheme that provides monthly financial assistance to the woman head of a "
         "household. Applicants are generally expected to be Karnataka residents and the woman recorded as head of the family "
         "on the ration card. Households where the woman or her husband pays income tax or files GST returns are generally "
         "excluded.\n\nSAMPLE CONTENT: verify the current eligibility rules, benefit amount, required documents and the "
         "official application channel against the latest government order before giving advice."),
        ("anna-bhagya-summary", "Anna Bhagya - scheme summary (sample)", "FOOD", "en", False, True, "",
         "Anna Bhagya provides food grains (and, at times, cash in lieu of part of the grain) to eligible ration card holders "
         "in Karnataka, typically Antyodaya (AAY) and priority household (BPL) card holders.\n\nSAMPLE CONTENT: confirm the current "
         "entitlement and rules with the Food, Civil Supplies & Consumer Affairs department."),
        ("gruha-jyothi-summary", "Gruha Jyothi - scheme summary (sample)", "ELEC", "en", False, True, "",
         "Gruha Jyothi offers free electricity up to a usage limit for domestic consumers in Karnataka, calculated from the "
         "household's past average consumption. Consumption above the eligible limit is billed.\n\nSAMPLE CONTENT: verify the "
         "unit limit and registration process with the electricity supply company."),
        ("documents-certificates", "Documents usually needed for income and caste certificates (sample)", "REVENUE", "en", False, True, "",
         "Applications for income or caste certificates generally require proof of identity, proof of address, a ration card "
         "or family details, and supporting documents such as salary certificates or land records for income.\n\nSAMPLE "
         "CONTENT: the exact list varies by service; check the official service portal before applying."),
        ("water-complaint-guidance", "Reporting contaminated water - what to do (sample)", "WATER", "en", False, True, "",
         "If tap water looks dirty, smells unusual or is discoloured, do not drink it without boiling. Report it with your "
         "locality and how long it has been happening. Contaminated water is treated as high priority because of the health "
         "risk.\n\nSAMPLE CONTENT pending verification by the water utility."),
        ("bidi-deepa-kn", "ಬೀದಿ ದೀಪ ದೂರು ಹೇಗೆ ನೀಡುವುದು (ಮಾದರಿ)", "STREETLIGHT", "kn", False, True, "",
         "ಬೀದಿ ದೀಪ ಕೆಟ್ಟಿದ್ದರೆ ಕಂಬದ ಸಂಖ್ಯೆ ಅಥವಾ ಹತ್ತಿರದ ಗುರುತು ಸ್ಥಳವನ್ನು ತಿಳಿಸಿ ದೂರು ನೀಡಿ. ದೂರು ಸಂಖ್ಯೆಯನ್ನು ಬಳಸಿ ಸ್ಥಿತಿಯನ್ನು "
         "ಪರಿಶೀಲಿಸಬಹುದು.\n\nಮಾದರಿ ವಿಷಯ: ಅಧಿಕೃತವಾಗಿ ಪರಿಶೀಲಿಸಬೇಕಾಗಿದೆ."),
    ],
    "tn-chennai": [
        ("grievance-procedure", "How grievance redressal works on this platform", "", "en", True, False, "Platform documentation",
         "Every complaint receives a ticket ID immediately after you confirm it. Complaints are routed to the responsible "
         "department, or to a nodal officer for manual review when the category is unclear. Unresolved tickets are escalated "
         "automatically when the SLA for their priority is breached. You can reject a closure and reopen the ticket."),
        ("sla-policy", "Service-level timelines configured on this platform", "", "en", True, False, "Platform configuration (SLA table)",
         "Emergency: first response 1 hour, resolution 4 hours. High: 4 hours / 24 hours. Medium: 24 hours / 72 hours. "
         "Low: 48 hours / 7 days. These are the demo configuration values of this deployment."),
        ("old-age-pension-summary", "Old age pension - general guidance (sample)", "WELFARE", "en", False, True, "",
         "State old age pension schemes generally support elderly persons with limited income who meet age and residence "
         "criteria. SAMPLE CONTENT: check the current Tamil Nadu scheme rules and the official application channel."),
        ("theru-vilakku-ta", "தெரு விளக்கு புகார் வழிகாட்டி (மாதிரி)", "STREETLIGHT", "ta", False, True, "",
         "தெரு விளக்கு எரியவில்லை என்றால் கம்ப எண் அல்லது அருகிலுள்ள அடையாளத்துடன் புகார் செய்யவும். புகார் எண்ணைக் கொண்டு "
         "நிலையை அறியலாம். மாதிரி உள்ளடக்கம்: அதிகாரப்பூர்வ சரிபார்ப்பு தேவை."),
    ],
}

_YES_NO = [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]

SCHEMES = {
    "ka-bengaluru": [
        {"code": "gruha_lakshmi", "names": {"en": "Gruha Lakshmi", "kn": "ಗೃಹ ಲಕ್ಷ್ಮಿ", "hi": "गृह लक्ष्मी"},
         "service_category": "women_child", "department": "Women & Child Development (verify)",
         "summary": "Monthly financial assistance to the woman head of the household (illustrative summary).",
         "benefits": "Benefit amount: verify on the official source before quoting.",
         "documents": ["Ration card showing the woman as head of family", "Aadhaar-linked bank account", "Proof of residence"],
         "steps": ["Confirm eligibility with the official notification", "Apply through the official channel named by the department",
                   "Track application status through the official channel"],
         "questions": [{"id": "resident", "text": "Do you live in Karnataka?", "type": "choice", "options": _YES_NO},
                       {"id": "gender", "text": "Are you a woman?", "type": "choice", "options": _YES_NO},
                       {"id": "head_of_household", "text": "Are you recorded as head of family on the ration card?", "type": "choice", "options": _YES_NO},
                       {"id": "income_tax", "text": "Do you or your husband pay income tax or file GST returns?", "type": "choice", "options": _YES_NO}],
         "rules": [{"question": "resident", "op": "eq", "value": "yes", "type": "requirement", "explain": "Karnataka resident"},
                   {"question": "gender", "op": "eq", "value": "yes", "type": "requirement", "explain": "Applicant is a woman"},
                   {"question": "head_of_household", "op": "eq", "value": "yes", "type": "requirement", "explain": "Head of family on ration card"},
                   {"question": "income_tax", "op": "eq", "value": "yes", "type": "exclusion", "explain": "Income-tax / GST payer households are excluded"}]},
        {"code": "anna_bhagya", "names": {"en": "Anna Bhagya", "kn": "ಅನ್ನ ಭಾಗ್ಯ", "hi": "अन्न भाग्य"},
         "service_category": "food", "department": "Food, Civil Supplies & Consumer Affairs (verify)",
         "summary": "Food grain support for eligible ration card holders (illustrative summary).",
         "benefits": "Entitlement: verify current quantity / cash component on the official source.",
         "documents": ["Ration card (AAY / priority household)", "Aadhaar linked to ration card"],
         "steps": ["Check your ration card category", "Collect entitlement at your fair price shop", "Report issues as a grievance"],
         "questions": [{"id": "resident", "text": "Do you live in Karnataka?", "type": "choice", "options": _YES_NO},
                       {"id": "card_type", "text": "What type of ration card do you have?", "type": "choice",
                        "options": [{"value": "AAY", "label": "Antyodaya (AAY)"}, {"value": "BPL", "label": "Priority / BPL"},
                                    {"value": "APL", "label": "APL / other"}, {"value": "none", "label": "No card"}]}],
         "rules": [{"question": "resident", "op": "eq", "value": "yes", "type": "requirement", "explain": "Karnataka resident"},
                   {"question": "card_type", "op": "in", "value": ["AAY", "BPL"], "type": "requirement", "explain": "AAY or priority household card"}]},
        {"code": "gruha_jyothi", "names": {"en": "Gruha Jyothi", "kn": "ಗೃಹ ಜ್ಯೋತಿ", "hi": "गृह ज्योति"},
         "service_category": "energy", "department": "Energy Department / ESCOMs (verify)",
         "summary": "Free domestic electricity up to an eligible usage limit (illustrative summary).",
         "benefits": "Unit limit and calculation: verify on the official source.",
         "documents": ["Electricity account number", "Aadhaar"],
         "steps": ["Confirm your connection is domestic", "Register through the official channel", "Check bills for the benefit"],
         "questions": [{"id": "resident", "text": "Do you live in Karnataka?", "type": "choice", "options": _YES_NO},
                       {"id": "domestic", "text": "Is the connection a domestic (household) connection?", "type": "choice", "options": _YES_NO},
                       {"id": "avg_units", "text": "Average monthly units used (from your bill)", "type": "number"}],
         "rules": [{"question": "resident", "op": "eq", "value": "yes", "type": "requirement", "explain": "Karnataka resident"},
                   {"question": "domestic", "op": "eq", "value": "yes", "type": "requirement", "explain": "Domestic connection"},
                   {"question": "avg_units", "op": "lte", "value": 200, "type": "requirement", "explain": "Average use within the seed limit (200 units - verify)"}]},
        {"code": "shakti", "names": {"en": "Shakti", "kn": "ಶಕ್ತಿ", "hi": "शक्ति"},
         "service_category": "transport", "department": "Transport Department (verify)",
         "summary": "Free travel for women on eligible state-run buses (illustrative summary).",
         "benefits": "Eligible bus categories: verify on the official source.",
         "documents": ["Identity / residence proof as required by the transport corporation"],
         "steps": ["Carry valid identity proof when travelling", "Check which bus services are covered"],
         "questions": [{"id": "resident", "text": "Do you live in Karnataka?", "type": "choice", "options": _YES_NO},
                       {"id": "gender", "text": "Are you a woman?", "type": "choice", "options": _YES_NO}],
         "rules": [{"question": "resident", "op": "eq", "value": "yes", "type": "requirement", "explain": "Karnataka resident"},
                   {"question": "gender", "op": "eq", "value": "yes", "type": "requirement", "explain": "Woman passenger"}]},
        {"code": "yuva_nidhi", "names": {"en": "Yuva Nidhi", "kn": "ಯುವ ನಿಧಿ", "hi": "युवा निधि"},
         "service_category": "education", "department": "Skill Development (verify)",
         "summary": "Unemployment allowance for eligible graduates and diploma holders (illustrative summary).",
         "benefits": "Allowance amounts, qualifying years and duration: verify on the official source.",
         "documents": ["Degree / diploma certificate", "Proof of domicile", "Self-declaration of unemployment"],
         "steps": ["Check your year of passing against the notification", "Register through the official channel"],
         "questions": [{"id": "resident", "text": "Are you domiciled in Karnataka?", "type": "choice", "options": _YES_NO},
                       {"id": "qualification", "text": "Highest qualification", "type": "choice",
                        "options": [{"value": "graduate", "label": "Graduate"}, {"value": "diploma", "label": "Diploma"},
                                    {"value": "other", "label": "Other"}]},
                       {"id": "employed", "text": "Are you currently employed or self-employed?", "type": "choice", "options": _YES_NO},
                       {"id": "higher_studies", "text": "Are you pursuing higher studies?", "type": "choice", "options": _YES_NO}],
         "rules": [{"question": "resident", "op": "eq", "value": "yes", "type": "requirement", "explain": "Karnataka domicile"},
                   {"question": "qualification", "op": "in", "value": ["graduate", "diploma"], "type": "requirement", "explain": "Graduate or diploma holder"},
                   {"question": "employed", "op": "eq", "value": "yes", "type": "exclusion", "explain": "Employed persons excluded"},
                   {"question": "higher_studies", "op": "eq", "value": "yes", "type": "exclusion", "explain": "Students in higher studies excluded"}]},
    ],
    "tn-chennai": [
        {"code": "old_age_pension", "names": {"en": "Old age pension (illustrative)", "ta": "முதியோர் ஓய்வூதியம்"},
         "service_category": "pensions", "department": "Revenue / Social Security (verify)",
         "summary": "Monthly pension support for eligible elderly persons (illustrative; add verified rules).",
         "benefits": "Verify the amount and rules on the official source.", "documents": ["Age proof", "Residence proof", "Bank account"],
         "steps": ["Check eligibility with the local revenue office", "Apply through the official channel"],
         "questions": [{"id": "age", "text": "Your age in years", "type": "number"},
                       {"id": "resident", "text": "Do you live in Tamil Nadu?", "type": "choice", "options": _YES_NO}],
         "rules": [{"question": "resident", "op": "eq", "value": "yes", "type": "requirement", "explain": "Tamil Nadu resident"},
                   {"question": "age", "op": "gte", "value": 60, "type": "requirement", "explain": "Age 60 or above (seed rule - verify)"}]},
    ],
}

# Service directory placeholders so every service category is navigable; no rules = no eligibility guesswork.
DIRECTORY = [("health", "Health benefit / insurance schemes"), ("education", "Scholarships"),
             ("labour", "Labour welfare board services"), ("housing", "Housing schemes"),
             ("agriculture", "Farmer support schemes"), ("revenue", "Revenue certificates (income, caste, residence)"),
             ("social_welfare", "Social welfare schemes"), ("public_works", "Public works requests")]

TEMPLATES = [
    ("response_letter", "en", "Grievance response letter",
     "{{authority}}\nDate: {{date}}\n\nTo,\n{{citizen_name}}\n\nSubject: Response to your complaint {{ticket_id}} - {{category}}\n\n"
     "Your complaint registered on {{filed_on}} regarding {{category}} at {{location}} has been examined by the "
     "{{department}}.\n\nAction taken: {{resolution}}\n\nCurrent status: {{status}}\n\nIf you are not satisfied, you may "
     "reject the closure from the citizen portal and the complaint will be reopened.\n\nYours faithfully,\n{{officer_name}}\n"
     "[Signature: to be signed manually by the competent officer]"),
    ("response_letter", "kn", "ದೂರಿಗೆ ಉತ್ತರ ಪತ್ರ",
     "{{authority}}\nದಿನಾಂಕ: {{date}}\n\nಗೆ,\n{{citizen_name}}\n\nವಿಷಯ: ನಿಮ್ಮ ದೂರು {{ticket_id}} - {{category}} ಕುರಿತು\n\n"
     "{{filed_on}} ರಂದು ದಾಖಲಾದ {{location}} ನಲ್ಲಿನ {{category}} ಕುರಿತ ನಿಮ್ಮ ದೂರನ್ನು {{department}} ಪರಿಶೀಲಿಸಿದೆ.\n\n"
     "ಕೈಗೊಂಡ ಕ್ರಮ: {{resolution}}\n\nಪ್ರಸ್ತುತ ಸ್ಥಿತಿ: {{status}}\n\nತೃಪ್ತಿಯಿಲ್ಲದಿದ್ದರೆ ಪೋರ್ಟಲ್‌ನಲ್ಲಿ ಮುಕ್ತಾಯವನ್ನು ತಿರಸ್ಕರಿಸಬಹುದು.\n\n"
     "{{officer_name}}\n[ಸಹಿ: ಸಕ್ಷಮ ಅಧಿಕಾರಿಯಿಂದ ಕೈಯಾರೆ]"),
    ("response_letter", "ta", "புகாருக்கான பதில் கடிதம்",
     "{{authority}}\nநாள்: {{date}}\n\nபெறுநர்,\n{{citizen_name}}\n\nபொருள்: உங்கள் புகார் {{ticket_id}} - {{category}}\n\n"
     "{{filed_on}} அன்று பதிவு செய்யப்பட்ட {{location}} பகுதியின் {{category}} தொடர்பான உங்கள் புகாரை {{department}} "
     "ஆய்வு செய்தது.\n\nஎடுக்கப்பட்ட நடவடிக்கை: {{resolution}}\n\nதற்போதைய நிலை: {{status}}\n\n{{officer_name}}\n"
     "[கையொப்பம்: அதிகாரி கைமுறையாக]"),
    ("notice", "en", "Public notice - planned works",
     "{{authority}}\nPUBLIC NOTICE\nDate: {{date}}\n\nThe {{department}} will carry out works related to {{category}} at "
     "{{location}}. Reference: {{ticket_id}}.\n\nCitizens are requested to cooperate.\n\n{{officer_name}}\n"
     "[To be approved and signed manually before publication]"),
    ("notice", "kn", "ಸಾರ್ವಜನಿಕ ಪ್ರಕಟಣೆ",
     "{{authority}}\nಸಾರ್ವಜನಿಕ ಪ್ರಕಟಣೆ\nದಿನಾಂಕ: {{date}}\n\n{{location}} ನಲ್ಲಿ {{category}} ಕುರಿತ ಕಾಮಗಾರಿಯನ್ನು {{department}} "
     "ಕೈಗೊಳ್ಳಲಿದೆ. ಉಲ್ಲೇಖ: {{ticket_id}}.\n\n{{officer_name}}\n[ಪ್ರಕಟಣೆಗೆ ಮೊದಲು ಅನುಮೋದನೆ ಮತ್ತು ಸಹಿ ಅಗತ್ಯ]"),
]

INTEGRATIONS = [
    ("llm", "LLM provider (OpenAI-compatible adapter)", "AI", "planned", "app.services.llm",
     "Adapter implemented; set LLM_PROVIDER/LLM_BASE_URL/LLM_API_KEY/LLM_MODEL. Without it, the transparent rule-based demo classifier is used and labelled."),
    ("web_speech", "Browser speech recognition (Web Speech API)", "Speech", "configured_unverified", "frontend/js/voice.js",
     "Works only in browsers that support it; Indian-language coverage varies by browser/device. Transcript is always shown for confirmation."),
    ("bhashini", "Bhashini / AI4Bharat speech & translation", "Speech", "planned", "STT_PROVIDER / TRANSLATION_PROVIDER",
     "Requires approved credentials. Not connected."),
    ("otp_sms", "SMS OTP gateway", "Messaging", "simulated", "OTP_PROVIDER=demo", "Demo shows the OTP on screen. Real SMS needs a DLT-registered provider."),
    ("sms_updates", "SMS status updates", "Messaging", "simulated", "SMS_PROVIDER", "Status notifications are recorded as simulated events."),
    ("whatsapp", "WhatsApp Business updates / inbox", "Messaging", "simulated", "WHATSAPP_PROVIDER", "Channel records are labelled simulated."),
    ("telephony", "Telephony (SIP / WebRTC / Asterisk)", "Call centre", "simulated", "app.services.callcentre.TelephonyProvider",
     "Agent hub uses clearly-labelled simulated calls. Provider adapter interface is defined."),
    ("pdf_text", "PDF text extraction (local pypdf)", "Documents", "connected_tested", "app.services.kb.extract_text",
     "Covered by automated tests."),
    ("ocr", "OCR for scanned documents / images", "Documents", "planned", "OCR_PROVIDER", "Images are stored; OCR requires a configured provider."),
    ("vector_store", "Vector store (Qdrant / FAISS) + embeddings", "AI", "planned", "app.services.kb.search",
     "Local BM25 retrieval is used and tested. Vector search not configured."),
    ("prometheus", "Prometheus metrics endpoint (/metrics)", "Monitoring", "connected_tested", "app.routers.health.metrics",
     "Endpoint exposed and covered by tests. External Prometheus/Grafana scraping is up to the deployer."),
    ("grafana", "Grafana dashboards", "Monitoring", "planned", "", "Not configured."),
    ("digilocker", "DigiLocker", "Identity", "planned", "", "Requires government approval. Not connected."),
    ("aadhaar_ekyc", "Aadhaar e-KYC", "Identity", "planned", "", "Requires licensed AUA/KUA arrangement. Not connected."),
    ("state_sso", "State SSO / staff MFA (e.g. KSDC)", "Identity", "planned", "", "Local password auth is used in demo mode."),
    ("eoffice", "State e-Office connector", "e-Office", "planned", "", "Draft/file workflow is internal; no external e-Office link."),
    ("dsc", "Digital signature (DSC / eSign)", "e-Office", "planned", "", "Drafts are never signed by the system."),
    ("cpgrams", "CPGRAMS / state grievance portal sync", "Grievance", "planned", "", "Not connected."),
    ("seva_sindhu", "Seva Sindhu", "Service portals", "planned", "", "Listed on the monitoring page as planned only; never probed."),
    ("gis", "Ward boundary / geocoding service", "GIS", "simulated", "app.services.geo",
     "Demo rectangular ward boundaries are configured and flagged as demo; replace with official GIS layers."),
]
