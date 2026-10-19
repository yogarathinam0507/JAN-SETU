"""Transparent, versioned lexicon for the offline rule-based demo classifier.

This is NOT a trained model. It is a deterministic, explainable fallback used when no AI provider is
configured. Every match is shown to the user in the TrustShield panel. Patterns are regular expressions
(case-insensitive); Indic-script patterns are matched as substrings.
"""

LEXICON_VERSION = "lexicon-2026.10-r4"

# category code -> list of (pattern, weight, language)
LEXICON: dict[str, list[tuple[str, float, str]]] = {
    "streetlight": [
        (r"\bstreet\s?lights?\b", 3, "en"), (r"\bstreet\s?lamps?\b", 3, "en"), (r"\blamp\s?posts?\b", 2.5, "en"),
        (r"\blight\s?poles?\b", 2.5, "en"), (r"\blights? (are |is )?not working\b", 1.5, "en"),
        (r"\b(road|street|lane) is (very )?dark\b", 1.5, "en"), (r"\btheru vilakk?u\b", 3, "ta-Latn"),
        (r"स्ट्रीट\s?लाइट", 3, "hi"), (r"बत्ती", 1.5, "hi"), (r"खंभे", 1.5, "hi"),
        (r"ಬೀದಿ\s?ದೀಪ", 3, "kn"), (r"ಸ್ಟ್ರೀಟ್\s?ಲೈಟ್", 3, "kn"),
        (r"தெரு\s?விளக்கு", 3, "ta"),
    ],
    "power_hazard": [
        (r"\bspark(s|ing|ed)?\b", 3, "en"), (r"\blive wires?\b", 3, "en"), (r"\belectrocut", 3, "en"),
        (r"\b(electric|power) (shock|wire fallen|wire on road)\b", 2.5, "en"), (r"\btransformers?\b", 1, "en"),
        (r"\b(wire|cable)s? (hanging|fallen|snapped|cut)\b", 2, "en"),
        (r"चिंगारी", 3, "hi"), (r"स्पार्क", 3, "hi"), (r"नंगा तार", 3, "hi"), (r"करंट", 1.5, "hi"),
        (r"ट्रांसफ(ा|ॉ)र्मर", 1, "hi"),
        (r"ಕಿಡಿ", 3, "kn"), (r"ಸ್ಪಾರ್ಕ್", 3, "kn"), (r"ಟ್ರಾನ್ಸ್‌?ಫಾರ್ಮರ್", 1, "kn"), (r"ವಿದ್ಯುತ್ ತಂತಿ", 2, "kn"),
        (r"தீப்பொறி", 3, "ta"), (r"மின்\s?கம்பி", 2, "ta"), (r"மின்மாற்றி", 1, "ta"), (r"டிரான்ஸ்ஃ?பார்மர்", 1, "ta"),
        (r"ஸ்பார்க்", 3, "ta"),
    ],
    "power_outage": [
        (r"\bpower cut\b", 3, "en"), (r"\bno (power|electricity|current)\b", 3, "en"), (r"\bpower (outage|failure)\b", 3, "en"),
        (r"\b(low|high|fluctuating) voltage\b", 2.5, "en"), (r"\belectricity (gone|not there|cut)\b", 2.5, "en"),
        (r"\btransformers?\b", 1, "en"), (r"\bbijli\b", 2, "hi-Latn"), (r"\bcurrent (illa|hogide|ille)\b", 3, "kn-Latn"),
        (r"बिजली", 2, "hi"), (r"बिजली (नहीं|गुल|कटौती)", 3, "hi"),
        (r"ವಿದ್ಯುತ್ (ಇಲ್ಲ|ಕಡಿತ)", 3, "kn"), (r"ಕರೆಂಟ್ ಇಲ್ಲ", 3, "kn"),
        (r"மின்சாரம் இல்லை", 3, "ta"), (r"மின்\s?வெட்டு", 3, "ta"), (r"கரண்ட் இல்லை", 3, "ta"),
    ],
    "water_quality": [
        (r"\b(dirty|muddy|contaminated|polluted|smelly|foul|yellow|brown|black) (tap |drinking )?water\b", 3, "en"),
        (r"\bwater (is |from the tap is )?(dirty|muddy|contaminated|smelly|yellow|brown|black)\b", 3, "en"),
        (r"\bcontaminat", 2, "en"), (r"\bsewage mixed\b", 3, "en"), (r"\bfrom the tap\b", 1, "en"),
        (r"गंदा पानी", 3, "hi"), (r"दूषित", 2.5, "hi"), (r"बदबूदार पानी", 3, "hi"), (r"मटमैला", 2.5, "hi"),
        (r"ಕಲುಷಿತ", 3, "kn"), (r"(ಕೊಳಕು|ಗಲೀಜು) ನೀರು", 3, "kn"),
        (r"அசுத்தமான (தண்ணீர்|நீர்)", 3, "ta"), (r"கலங்கிய (தண்ணீர்|நீர்)", 3, "ta"),
        (r"அழுக்கு (தண்ணீர்|நீர்)", 3, "ta"), (r"கழிவுநீர் கலந்த", 3, "ta"),
    ],
    "water_supply": [
        (r"\bno (drinking )?water\b", 3, "en"), (r"\bwater (is )?not (coming|available)\b", 3, "en"),
        (r"\bwater supply\b", 2, "en"), (r"\blow (water )?pressure\b", 2, "en"), (r"\b(pipe|pipeline) (burst|leak)", 2.5, "en"),
        (r"\bwater leak", 2, "en"), (r"\bpaani nahi\b", 3, "hi-Latn"), (r"\bneeru (illa|barthilla)\b", 3, "kn-Latn"),
        (r"पानी नहीं", 3, "hi"), (r"पानी की (आपूर्ति|सप्लाई)", 2.5, "hi"), (r"पाइप लीक", 2.5, "hi"),
        (r"ನೀರು (ಬರುತ್ತಿಲ್ಲ|ಇಲ್ಲ)", 3, "kn"), (r"ನೀರಿನ ಪೂರೈಕೆ", 2, "kn"),
        (r"(தண்ணீர்|குடிநீர்) (வரவில்லை|இல்லை)", 3, "ta"),
    ],
    "sewage": [
        (r"\bsewage\b", 2.5, "en"), (r"\bsewer", 2.5, "en"), (r"\bdrainage overflow", 3, "en"), (r"\bmanholes?\b", 2.5, "en"),
        (r"\b(ugd|underground drainage)\b", 2.5, "en"), (r"\bdrain (is )?overflowing\b", 2.5, "en"),
        (r"सीवर", 2.5, "hi"), (r"नाली", 2, "hi"), (r"मैनहोल", 2.5, "hi"),
        (r"ಒಳಚರಂಡಿ", 3, "kn"), (r"ಮ್ಯಾನ್‌?ಹೋಲ್", 2.5, "kn"),
        (r"கழிவுநீர்", 2, "ta"), (r"சாக்கடை", 2.5, "ta"),
    ],
    "garbage": [
        (r"\bgarbage\b", 3, "en"), (r"\btrash\b", 2.5, "en"), (r"\brubbish\b", 2.5, "en"), (r"\bwaste\b", 1.5, "en"),
        (r"\bnot (been )?(collected|cleared|picked)\b", 1.5, "en"), (r"\bdust ?bins?\b", 2, "en"), (r"\blitter", 2, "en"),
        (r"\bdump(ing|ed)?\b", 1.5, "en"), (r"\bkachra\b", 3, "hi-Latn"), (r"\bkuppai\b", 3, "ta-Latn"),
        (r"कचरा", 3, "hi"), (r"कूड़ा", 3, "hi"), (r"ಕಸ", 3, "kn"), (r"குப்பை", 3, "ta"),
    ],
    "roads": [
        (r"\bpot ?holes?\b", 3, "en"), (r"\b(road|street) (is )?(damaged|broken|caved)\b", 3, "en"),
        (r"\b(broken|damaged) road\b", 3, "en"), (r"\broad repair\b", 2.5, "en"), (r"\bfootpath\b", 1.5, "en"),
        (r"\bspeed breaker\b", 2, "en"), (r"\bgaddh?a\b", 2.5, "hi-Latn"), (r"\bgundi\b", 2.5, "kn-Latn"),
        (r"गड्ढा", 3, "hi"), (r"गड्ढे", 3, "hi"), (r"सड़क (टूटी|खराब)", 3, "hi"),
        (r"ಗುಂಡಿ", 3, "kn"), (r"ರಸ್ತೆ ಹಾಳ", 3, "kn"),
        (r"(சாலை|ரோடு)(யில்)? (குழி|பள்ளம்|சேதம்)", 3, "ta"), (r"பள்ளம்", 2, "ta"),
    ],
    "mosquito": [
        (r"\bmosquito(es)?\b", 3, "en"), (r"\bdengue\b", 2.5, "en"), (r"\bmalaria\b", 2.5, "en"),
        (r"\bbreeding\b", 1.5, "en"), (r"\bfogging\b", 2.5, "en"), (r"\bstagnant water\b", 1.5, "en"),
        (r"\bmachh?ar\b", 3, "hi-Latn"),
        (r"मच्छर", 3, "hi"), (r"डेंगू", 2.5, "hi"), (r"ಸೊಳ್ಳೆ", 3, "kn"), (r"ಡೆಂಗ್ಯೂ", 2.5, "kn"),
        (r"கொசு", 3, "ta"), (r"டெங்கு", 2.5, "ta"),
    ],
    "stray_animals": [
        (r"\bstray (dogs?|cattle|cows?|animals?)\b", 3, "en"), (r"\bdog ?bites?\b", 3, "en"), (r"\bdogs?\b", 1.5, "en"),
        (r"\brabi(d|es)\b", 2.5, "en"), (r"\bmonkeys?\b", 2, "en"), (r"\bnaa?y(i|e)\b", 2.5, "kn-Latn"),
        (r"आवारा (कुत्त|पशु|गाय)", 3, "hi"), (r"कुत्त", 1.5, "hi"),
        (r"ಬೀದಿ ನಾಯಿ", 3, "kn"), (r"ನಾಯಿ", 1.5, "kn"), (r"தெரு\s?நாய்", 3, "ta"), (r"நாய்", 1.5, "ta"),
    ],
    "storm_drain": [
        (r"\bflood(ed|ing)?\b", 2.5, "en"), (r"\bwater ?logg(ed|ing)\b", 3, "en"), (r"\bstorm ?water\b", 2.5, "en"),
        (r"\b(drain|drains|nala|nullah) (is )?(blocked|clogged|choked)\b", 2.5, "en"), (r"\binundat", 2.5, "en"),
        (r"बाढ़", 3, "hi"), (r"जलभराव", 3, "hi"), (r"ಪ್ರವಾಹ", 3, "kn"), (r"ರಾಜಕಾಲುವೆ", 2.5, "kn"),
        (r"வெள்ளம்", 3, "ta"), (r"மழைநீர் தேங்", 3, "ta"),
    ],
    "fallen_tree": [
        (r"\btree (has )?(fell|fallen|uprooted|collapsed)\b", 3, "en"), (r"\bfallen (tree|branch)\b", 3, "en"),
        (r"\b(tree )?branch(es)? (fell|fallen|hanging)\b", 2.5, "en"), (r"\btree cutting\b", 2, "en"),
        (r"पेड़ गिर", 3, "hi"), (r"ಮರ ಬಿದ್ದ", 3, "kn"), (r"மரம் விழு", 3, "ta"),
    ],
    "fire": [
        (r"\bfire\b", 3, "en"), (r"\b(heavy |thick )?smoke\b", 2, "en"), (r"\bburning\b", 2, "en"),
        (r"\bgas (leak|cylinder)", 3, "en"), (r"\bblaze\b", 3, "en"),
        (r"आग", 3, "hi"), (r"धुआं", 2, "hi"), (r"गैस रिसाव", 3, "hi"),
        (r"ಬೆಂಕಿ", 3, "kn"), (r"ಹೊಗೆ", 2, "kn"), (r"தீ விபத்து", 3, "ta"), (r"புகை", 2, "ta"), (r"தீ பற்றி", 3, "ta"),
    ],
    "public_toilet": [
        (r"\bpublic toilets?\b", 3, "en"), (r"\burinals?\b", 2.5, "en"), (r"\btoilet\b", 1.5, "en"),
        (r"शौचालय", 3, "hi"), (r"ಶೌಚಾಲಯ", 3, "kn"), (r"கழிப்பறை", 3, "ta"),
    ],
    "property_tax": [
        (r"\bproperty tax\b", 3, "en"), (r"\bkhata\b", 3, "en"), (r"\btax receipt\b", 2.5, "en"),
        (r"संपत्ति कर", 3, "hi"), (r"ಆಸ್ತಿ ತೆರಿಗೆ", 3, "kn"), (r"ಖಾತಾ", 3, "kn"), (r"சொத்து வரி", 3, "ta"),
    ],
    "ration": [
        (r"\bration\b", 3, "en"), (r"\bfair price shop\b", 3, "en"), (r"\bpds\b", 2.5, "en"),
        (r"राशन", 3, "hi"), (r"ಪಡಿತರ", 3, "kn"), (r"ರೇಷನ್", 3, "kn"), (r"ரேஷன்", 3, "ta"), (r"நியாய விலை", 3, "ta"),
    ],
    "pension": [
        (r"\bpension\b", 3, "en"), (r"\bold age (allowance|pension)\b", 3, "en"),
        (r"पेंशन", 3, "hi"), (r"ಪಿಂಚಣಿ", 3, "kn"), (r"ஓய்வூதியம்", 3, "ta"),
    ],
    "bus": [
        (r"\bbus(es)? (not stopping|did not stop|late|not coming|overcrowded)\b", 3, "en"), (r"\bbus stop\b", 0.5, "en"),
        (r"\bconductor\b", 2, "en"), (r"\bbus\b", 1.0, "en"),
        (r"बस", 1.5, "hi"), (r"ಬಸ್", 1.5, "kn"), (r"பேருந்து", 2, "ta"),
    ],
}

# ---- broader everyday phrasing (r4) ----
_MORE = {
    "streetlight": [(r"\b(street|road|lane|area|park|colony|layout|cross) (is |are )?(very |completely )?dark\b", 2.5, "en"),
                    (r"\blights? (are |is )?not (working|burning|on)\b", 2, "en"), (r"\bno street ?lights?\b", 3, "en"),
                    (r"\blight poles?\b", 3, "en"), (r"\bstreet ?light", 3, "en"), (r"\blamp (is )?(off|broken|fused)\b", 2.5, "en")],
    "power_hazard": [(r"\b(electric(al)?|current|power|lamp) poles? (is |are )?(leaning|bent|broken|fallen|tilted|damaged|shaking)\b", 3, "en"),
                     (r"\bpoles? (is |are )?(leaning|tilted|about to fall)\b", 2.5, "en"),
                     (r"\b(branches|tree) touching (the )?(electric |power |live )?wires?\b", 3, "en"),
                     (r"\bwires? (are |is )?(sagging|loose|hanging low|touching)\b", 2.5, "en"), (r"\bshock\b", 2, "en")],
    "power_outage": [(r"\b(power|electricity|current) (is )?(gone|off|not there|cut)\b", 3, "en"), (r"\bfrequent power cuts?\b", 3, "en"),
                     (r"\bvoltage (problem|fluctuation|drop)\b", 3, "en")],
    "power_billing": [(r"\b(electricity|power|current|bescom|eb) bill", 3, "en"), (r"\bmeter (reading|is faulty|not working|is fast)\b", 3, "en"),
                      (r"\bbill (is )?(very |too )?(high|wrong|excess)", 2, "en"), (r"\bnew (power |electricity )?connection\b", 2.5, "en"),
                      (r"बिजली बिल", 3, "hi"), (r"ವಿದ್ಯುತ್ ಬಿಲ್", 3, "kn"), (r"மின் கட்டண", 3, "ta")],
    "water_quality": [(r"\bwater (is )?(coming )?(with|mixed with) (mud|dirt|worms|sewage|insects)\b", 3, "en"),
                      (r"\b(muddy|dirty|smelly|bad smelling|discoloured|discolored) water\b", 3, "en")],
    "water_supply": [(r"\bwater (problem|shortage|scarcity)\b", 3, "en"), (r"\bno water\b", 3, "en"), (r"\b(main |water )?pipe(line)? (is )?(leaking|broken|damaged)\b", 3, "en"),
                     (r"\bwater (is )?(wasting|overflowing from (the )?tank)\b", 2, "en"), (r"\bborewell\b", 2, "en")],
    "sewage": [(r"\bdrain(age|s)? (is |are )?(blocked|clogged|choked|overflowing|full|smelling|broken|open)\b", 3, "en"),
               (r"\b(open|overflowing|blocked|clogged|choked|stinking) (drain|drainage|nala|gutter)\b", 3, "en"),
               (r"\bdrainage\b", 2, "en"), (r"\bgutter\b", 2, "en"), (r"\bmanhole (is )?(open|without (a )?(lid|cover)|overflowing)\b", 3, "en"),
               (r"\b(foul |bad )?smell from (the )?(drain|drainage|gutter)\b", 2.5, "en")],
    "garbage": [(r"\bclean(ing)? (the )?(garbage|waste|area|road|street)\b", 2.5, "en"), (r"\bwaste (is )?(dumped|thrown|burning)\b", 2.5, "en"),
                (r"\b(debris|construction waste)\b", 2, "en"), (r"\bsweep(ing)?\b", 1.5, "en")],
    "roads": [(r"\broads?\b[^.]{0,30}\b(bad|damaged|broken|holes?|dug|digging|uneven|repair|worst|cracked)\b", 3, "en"),
              (r"\bholes? (in|on) the road\b", 3, "en"), (r"\broad (cutting|digging|work (left|incomplete))\b", 3, "en"),
              (r"\b(speed hump|road hump)\b", 2, "en"), (r"\bfootpath (is )?(broken|damaged)\b", 3, "en")],
    "fallen_tree": [(r"\b(branches?|trees?) (need|needs|require) (trimming|pruning|cutting)\b", 3, "en"), (r"\btree (trimming|pruning)\b", 3, "en"),
                    (r"\bdangerous tree\b", 3, "en"), (r"\btree (is )?(about to fall|leaning)\b", 3, "en")],
    "encroachment": [(r"\billegal (construction|building|structure|shop|extension)\b", 3, "en"), (r"\bunauthori[sz]ed (construction|building)\b", 3, "en"),
                     (r"\bencroach", 3, "en"), (r"\bfootpath (is )?(occupied|encroached|blocked) by\b", 3, "en"),
                     (r"\b(shops?|vendors?|hawkers?) (on|occupying|blocking) (the )?footpath\b", 3, "en"),
                     (r"अतिक्रमण", 3, "hi"), (r"ಒತ್ತುವರಿ", 3, "kn"), (r"ಅಕ್ರಮ ಕಟ್ಟಡ", 3, "kn"), (r"ஆக்கிரமிப்பு", 3, "ta")],
    "noise": [(r"\bloud (music|noise|speakers?|sound)\b", 3, "en"), (r"\bnoise( pollution)?\b", 2.5, "en"), (r"\bloudspeakers?\b", 3, "en"),
              (r"\bhonking\b", 2, "en"), (r"ध्वनि प्रदूषण|शोर", 3, "hi"), (r"ಶಬ್ದ ಮಾಲಿನ್ಯ", 3, "kn"), (r"ஒலி மாசு", 3, "ta")],
    "dead_animal": [(r"\bdead (dog|cat|cow|animal|rat|pig|bird|buffalo)s?\b", 3, "en"), (r"\bcarcass\b", 3, "en"),
                    (r"मरा हुआ (कुत्ता|जानवर)", 3, "hi"), (r"ಸತ್ತ (ನಾಯಿ|ಪ್ರಾಣಿ)", 3, "kn"), (r"இறந்த (நாய்|விலங்கு)", 3, "ta")],
}
for _code, _pats in _MORE.items():
    LEXICON.setdefault(_code, []).extend(_pats)

# Deterministic safety rules (independent of the classifier). Matching any => Emergency priority.
EMERGENCY_RULES: list[tuple[str, str, str]] = [
    ("R-EMG-01", r"\bspark(s|ing|ed)?\b|चिंगारी|स्पार्क|ಕಿಡಿ|ಸ್ಪಾರ್ಕ್|தீப்பொறி|ஸ்பார்க்", "Electrical sparking"),
    ("R-EMG-02", r"\blive wires?\b|\belectrocut|नंगा तार|ವಿದ್ಯುತ್ ತಂತಿ ಬಿದ್ದ|(wire|cable)s? (fallen|snapped) on (the )?road",
     "Exposed live wire / electrocution risk"),
    ("R-EMG-03", r"\bfire\b|\bblaze\b|आग|ಬೆಂಕಿ|தீ விபத்து|தீ பற்றி", "Fire"),
    ("R-EMG-04", r"\bgas (leak|leaking)|गैस रिसाव", "Gas leak"),
    ("R-EMG-05", r"\b(water|flood) (entering|inside) (the )?(house|home)s?\b|\bdrown|\bpeople (are )?trapped\b",
     "Flooding danger to people"),
    ("R-EMG-06", r"\bunconscious\b|\bheavy bleeding\b|\bnot breathing\b|\bheart attack\b", "Urgent medical risk"),
    ("R-EMG-07", r"\b(building|wall) (has )?collaps", "Structural collapse"),
]

# Risk modifiers raise Medium/Low to High (never lower anything).
RISK_RULES: list[tuple[str, str, str]] = [
    ("R-RISK-01", r"\b(school|hospital|children|kids|elderly|old people)\b|स्कूल|अस्पताल|बच्चे|ಶಾಲೆ|ಆಸ್ಪತ್ರೆ|ಮಕ್ಕಳು|பள்ளி|மருத்துவமனை|குழந்தை",
     "Vulnerable group or critical facility mentioned"),
    ("R-RISK-02", r"\b(attack(ed|ing)?|bit(ten|e) (a |my )?(child|person|man|woman))\b", "Physical harm reported"),
    ("R-RISK-03", r"\baccident\b|दुर्घटना|ಅಪಘಾತ|விபத்து", "Accident reported"),
]

TRANSLIT_HINTS = {
    "hi": ["bijli", "paani", "kachra", "nahi", "sadak", "gaddha", "machhar", "kutte", "hai"],
    "kn": ["illa", "neeru", "kasa", "beedi", "gundi", "barthilla", "hogide", "ide", "nayi"],
    "ta": ["illai", "thanni", "kuppai", "theru", "vilakku", "varala", "irukku"],
}

# Gold-labelled evaluation set (used by tests and the measured AI-evaluation report).
EVAL_DATASET_NAME = "triage-eval-v2 (60 labelled test examples)"
EVAL_DATASET: list[tuple[str, str, str, str | None]] = [
    # (language, text, expected category or "human_review", expected priority or None)
    ("en", "Streetlight not working for three days", "streetlight", "Medium"),
    ("en", "Transformer sparking near houses", "power_hazard", "Emergency"),
    ("en", "Dirty water from the tap", "water_quality", "High"),
    ("en", "Garbage not collected for a week", "garbage", "Medium"),
    ("en", "Large pothole after rain", "roads", "Medium"),
    ("en", "Mosquito breeding in stagnant water", "mosquito", "Medium"),
    ("en", "Stray dogs attacking people", "stray_animals", "High"),
    ("en", "asdkj qwe zzkx plmnb", "human_review", None),
    ("en", "What is the cricket score today", "human_review", None),
    ("en", "No electricity in our street since morning", "power_outage", "High"),
    ("en", "Water is not coming in our area for two days", "water_supply", "High"),
    ("en", "Sewage overflowing from the manhole on main road", "sewage", "High"),
    ("en", "Severe waterlogging on the underpass after rain", "storm_drain", "High"),
    ("en", "A big tree has fallen on the road blocking traffic", "fallen_tree", "High"),
    ("en", "Fire in the garbage dump behind the market", "fire", "Emergency"),
    ("en", "Live wire hanging near the bus stop", "power_hazard", "Emergency"),
    ("en", "Street lamp near the school is broken", "streetlight", "High"),
    ("en", "Overflowing dustbin and litter everywhere", "garbage", "Medium"),
    ("en", "The road is damaged and full of potholes", "roads", "Medium"),
    ("en", "Dengue cases rising, please do fogging", "mosquito", "Medium"),
    ("en", "Public toilet is locked and dirty", "public_toilet", "Medium"),
    ("en", "My property tax receipt is not generated", "property_tax", "Low"),
    ("en", "Ration shop did not give rice this month", "ration", "Medium"),
    ("en", "Old age pension not received for three months", "pension", "Medium"),
    ("hi", "हमारी गली की स्ट्रीट लाइट तीन दिन से खराब है", "streetlight", "Medium"),
    ("hi", "ट्रांसफार्मर से चिंगारी निकल रही है", "power_hazard", "Emergency"),
    ("hi", "नल से गंदा पानी आ रहा है", "water_quality", "High"),
    ("hi", "एक हफ्ते से कचरा नहीं उठाया गया", "garbage", "Medium"),
    ("hi", "सड़क पर बड़ा गड्ढा है", "roads", "Medium"),
    ("hi", "रुके हुए पानी में मच्छर पैदा हो रहे हैं", "mosquito", "Medium"),
    ("hi", "आवारा कुत्ते लोगों पर हमला कर रहे हैं", "stray_animals", "High"),
    ("hi", "दो दिन से पानी नहीं आ रहा", "water_supply", "High"),
    ("kn", "ನಮ್ಮ ರಸ್ತೆಯ ಬೀದಿ ದೀಪ ಮೂರು ದಿನಗಳಿಂದ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ", "streetlight", "Medium"),
    ("kn", "ಮನೆಗಳ ಹತ್ತಿರ ಟ್ರಾನ್ಸ್‌ಫಾರ್ಮರ್‌ನಿಂದ ಕಿಡಿ ಬರುತ್ತಿದೆ", "power_hazard", "Emergency"),
    ("kn", "ನಲ್ಲಿಯಲ್ಲಿ ಕಲುಷಿತ ನೀರು ಬರುತ್ತಿದೆ", "water_quality", "High"),
    ("kn", "ಒಂದು ವಾರದಿಂದ ಕಸ ಸಂಗ್ರಹಿಸಿಲ್ಲ", "garbage", "Medium"),
    ("kn", "ಮಳೆಯ ನಂತರ ರಸ್ತೆಯಲ್ಲಿ ದೊಡ್ಡ ಗುಂಡಿ", "roads", "Medium"),
    ("kn", "ನಿಂತ ನೀರಿನಲ್ಲಿ ಸೊಳ್ಳೆ ಉತ್ಪತ್ತಿಯಾಗುತ್ತಿದೆ", "mosquito", "Medium"),
    ("kn", "ಬೀದಿ ನಾಯಿಗಳು ಜನರ ಮೇಲೆ ದಾಳಿ ಮಾಡುತ್ತಿವೆ", "stray_animals", "High"),
    ("kn", "ಎರಡು ದಿನದಿಂದ ಕರೆಂಟ್ ಇಲ್ಲ", "power_outage", "High"),
    ("ta", "எங்கள் தெருவில் தெரு விளக்கு மூன்று நாட்களாக எரியவில்லை", "streetlight", "Medium"),
    ("ta", "வீடுகளுக்கு அருகில் மின்மாற்றியில் தீப்பொறி வருகிறது", "power_hazard", "Emergency"),
    ("ta", "குழாயில் அழுக்கு தண்ணீர் வருகிறது", "water_quality", "High"),
    ("ta", "ஒரு வாரமாக குப்பை அள்ளப்படவில்லை", "garbage", "Medium"),
    ("ta", "மழைக்குப் பிறகு சாலையில் பெரிய பள்ளம்", "roads", "Medium"),
    ("ta", "தேங்கிய நீரில் கொசு உற்பத்தி", "mosquito", "Medium"),
    ("ta", "தெரு நாய்கள் மக்களை தாக்குகின்றன", "stray_animals", "High"),
    ("ta", "இரண்டு நாட்களாக குடிநீர் வரவில்லை", "water_supply", "High"),
    ("en", "Road is very bad and full of holes", "roads", "Medium"),
    ("en", "Drainage is blocked and smelling", "sewage", "High"),
    ("en", "My street is very dark at night", "streetlight", "Medium"),
    ("en", "Electricity bill is very high this month", "power_billing", "Low"),
    ("en", "Illegal construction next to my house", "encroachment", "Medium"),
    ("en", "Loud music at night from the neighbour", "noise", "Medium"),
    ("en", "Dead dog lying on the road", "dead_animal", "High"),
    ("en", "Electric pole is leaning and may fall", "power_hazard", "Emergency"),
    ("en", "Water is coming with mud", "water_quality", "High"),
    ("en", "Footpath occupied by shops", "encroachment", "Medium"),
    ("en", "Branches need trimming near our house", "fallen_tree", "High"),
    ("en", "Overflowing drain in front of the market", "sewage", "High"),
]
