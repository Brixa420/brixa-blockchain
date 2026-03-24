"""
Wrath of Cali - Advanced Wallet Infrastructure
HD Wallets, Mnemonics, Multi-addr, Hardware Wallet Support
"""
import json
import time
import hashlib
import secrets
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from crypto import generate_keypair, get_address, sign, verify_signature, sha256
from core import Transaction

# Configuration
MAIN_NODE_URL = "http://localhost:5001"


# ========== MNEMONIC & HD WALLET ==========
class Mnemonic:
    """BIP-39 style mnemonics (simplified 12-word)"""
    
    WORDLIST = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
        "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
        "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
        "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
        "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
        "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album",
        "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone",
        "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among",
        "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle", "angry",
        "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique",
        "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april",
        "arch", "arctic", "arena", "argue", "arm", "armed", "armor", "army",
        "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact", "artist",
        "artwork", "ask", "aspect", "assault", "asset", "assist", "assume", "asthma",
        "athlete", "atom", "attack", "attend", "attitude", "attract", "auction", "audit",
        "august", "aunt", "author", "auto", "autumn", "average", "avocado", "avoid",
        "awake", "aware", "away", "awesome", "awful", "awkward", "axis", "baby",
        "bachelor", "bacon", "badge", "bag", "balance", "balcony", "ball", "bamboo",
        "banana", "banner", "bar", "barely", "bargain", "barrel", "base", "basic",
        "basket", "battle", "beach", "bean", "beauty", "because", "become", "beef",
        "before", "begin", "behave", "behind", "believe", "below", "belt", "bench",
        "benefit", "best", "betray", "better", "between", "beyond", "bicycle", "bid",
        "bike", "bind", "biology", "bird", "birth", "bitter", "black", "blade",
        "blame", "blanket", "blast", "bleak", "bless", "blind", "blood", "blossom",
        "blouse", "blue", "blur", "blush", "board", "boat", "body", "boil",
        "bomb", "bone", "bonus", "book", "boost", "border", "boring", "borrow",
        "boss", "bottom", "bounce", "box", "boy", "bracket", "brain", "brand",
        "brass", "brave", "bread", "breeze", "brick", "bridge", "brief", "bright",
        "bring", "brisk", "broccoli", "broken", "bronze", "broom", "brother", "brown",
        "brush", "bubble", "buddy", "budget", "buffalo", "build", "bulb", "bulk",
        "bullet", "bundle", "bunker", "burden", "burger", "burst", "bus", "business",
        "busy", "butter", "buyer", "buzz", "cabbage", "cabin", "cable", "cactus",
        "cage", "cake", "call", "calm", "camera", "camp", "can", "canal",
        "cancel", "candy", "cannon", "canoe", "canvas", "canyon", "capable", "capital",
        "captain", "car", "carbon", "card", "cargo", "carpet", "carry", "cart",
        "case", "cash", "casino", "castle", "casual", "cat", "catalog", "catch",
        "category", "cattle", "caught", "cause", "caution", "cave", "ceiling", "celery",
        "cement", "census", "century", "cereal", "certain", "chair", "chalk", "champion",
        "change", "chaos", "chapter", "charge", "chase", "chat", "cheap", "check",
        "cheese", "cherry", "chest", "chicken", "chief", "child", "chimney", "choice",
        "choose", "chronic", "chuckle", "chunk", "churn", "cigar", "cinnamon", "circle",
        "citizen", "city", "civil", "claim", "clap", "clarify", "claw", "clay",
        "clean", "clerk", "clever", "click", "client", "cliff", "climb", "clinic",
        "clip", "clock", "clog", "close", "cloth", "cloud", "clown", "club",
        "clump", "cluster", "clutch", "coach", "coast", "coconut", "code", "coffee",
        "coil", "coin", "collect", "color", "column", "combine", "come", "comfort",
        "comic", "common", "company", "concert", "conduct", "confirm", "congress", "connect",
        "consider", "control", "convince", "cook", "cool", "copper", "copy", "coral",
        "core", "corn", "corner", "correct", "cost", "cottage", "cotton", "couch",
        "country", "couple", "course", "cousin", "cover", "coyote", "crack", "cradle",
        "craft", "cram", "crane", "crash", "crater", "crawl", "crazy", "cream",
        "credit", "creek", "crew", "cricket", "crime", "crisp", "critic", "crop",
        "cross", "crouch", "crowd", "crucial", "cruel", "cruise", "crumble", "crunch",
        "crush", "cry", "crystal", "cube", "culture", "cup", "cupboard", "curious",
        "current", "curtain", "curve", "cushion", "custom", "cute", "cycle", "dad",
        "damage", "damp", "dance", "danger", "daring", "dash", "daughter", "dawn",
        "day", "deal", "debate", "debris", "decade", "december", "decide", "decline",
        "decorate", "decrease", "deer", "defense", "define", "defy", "degree", "delay",
        "deliver", "demand", "demise", "denial", "dentist", "deny", "depart", "depend",
        "deposit", "depth", "deputy", "derive", "describe", "desert", "design", "desk",
        "despair", "destroy", "detail", "detect", "develop", "device", "devote", "diagram",
        "dial", "diamond", "diary", "dice", "diesel", "diet", "differ", "digital",
        "dignity", "dilemma", "dinner", "dinosaur", "direct", "dirt", "disagree", "discover",
        "disease", "dish", "dismiss", "disorder", "display", "distance", "divert", "divide",
        "divorce", "dizzy", "doctor", "document", "dog", "doll", "dolphin", "domain",
        "donate", "donkey", "donor", "door", "dose", "double", "dove", "draft",
        "dragon", "drama", "draw", "dream", "dress", "drift", "drill", "drink",
        "drip", "drive", "drop", "drum", "dry", "duck", "dumb", "dune",
        "during", "dust", "dutch", "duty", "dwarf", "dynamic", "eager", "eagle",
        "early", "earn", "earth", "easily", "east", "easy", "echo", "ecology",
        "economy", "edge", "edit", "educate", "effort", "egg", "eight", "eject",
        "elastic", "elbow", "elder", "electric", "elegant", "element", "elephant", "elevator",
        "elite", "else", "embark", "embody", "embrace", "emerge", "emotion", "employ",
        "empower", "empty", "enable", "enact", "end", "endorse", "enemy", "energy",
        "enforce", "engage", "engine", "enhance", "enjoy", "enlist", "enough", "enrich",
        "enroll", "ensure", "enter", "entire", "entry", "envelope", "episode", "equal",
        "equip", "era", "erase", "erode", "erosion", "error", "erupt", "escape",
        "essay", "essence", "estate", "eternal", "ethics", "evidence", "evil", "evoke",
        "evolve", "exact", "example", "excess", "exchange", "excite", "exclude", "excuse",
        "execute", "exercise", "exhaust", "exhibit", "exile", "exist", "exit", "exotic",
        "expand", "expect", "expire", "explain", "expose", "express", "extend", "extra",
        "eye", "eyebrow", "fabric", "face", "faculty", "fade", "faint", "faith",
        "fall", "false", "fame", "family", "famous", "fan", "fancy", "fantasy",
        "farm", "fashion", "fat", "fatal", "father", "fatigue", "fault", "favorite",
        "feature", "february", "federal", "fee", "feed", "feel", "female", "fence",
        "festival", "fetch", "fever", "few", "fiber", "fiction", "field", "figure",
        "file", "film", "filter", "final", "find", "fine", "finger", "finish",
        "fire", "firm", "first", "fiscal", "fish", "fit", "fitness", "fix",
        "flag", "flame", "flash", "flat", "flavor", "flee", "flight", "flip",
        "float", "flock", "floor", "flower", "fluid", "flush", "fly", "foam",
        "focus", "fog", "foil", "fold", "follow", "food", "foot", "force",
        "forest", "forget", "fork", "fortune", "forum", "forward", "fossil", "foster",
        "found", "fox", "fragile", "frame", "frequent", "fresh", "friend", "fringe",
        "frog", "front", "frost", "frown", "frozen", "fruit", "fuel", "fun",
        "funny", "furnace", "fury", "future", "gadget", "gain", "galaxy", "gallery",
        "game", "gap", "garage", "garbage", "garden", "garlic", "gas", "gasp",
        "gate", "gather", "gauge", "gaze", "general", "genius", "genre", "gentle",
        "genuine", "gesture", "ghost", "giant", "gift", "giggle", "ginger", "giraffe",
        "girl", "give", "glad", "glance", "glare", "glass", "glide", "glimpse",
        "globe", "gloom", "glory", "glove", "glow", "glue", "goat", "goddess",
        "gold", "good", "goose", "gorilla", "gospel", "gossip", "govern", "gown",
        "grab", "grace", "grain", "grant", "grape", "grass", "gravity", "great",
        "green", "grid", "grief", "grit", "grocery", "group", "grow", "grunt",
        "guard", "guess", "guide", "guilt", "guitar", "gun", "gym", "habit",
        "hair", "half", "hammer", "hamster", "hand", "handle", "harbor", "hard",
        "harsh", "harvest", "hat", "have", "hawk", "hazard", "head", "health",
        "heart", "heavy", "hedgehog", "height", "helium", "hello", "helmet", "help",
        "hen", "hero", "hidden", "high", "hill", "hint", "hip", "hire",
        "history", "hobby", "hockey", "hold", "hole", "holiday", "hollow", "home",
        "honey", "hood", "hope", "horn", "horror", "horse", "hospital", "host",
        "hotel", "hour", "hover", "hub", "huge", "human", "humble", "humor",
        "hundred", "hungry", "hunt", "hurdle", "hurry", "hurt", "husband", "hybrid",
        "ice", "icon", "idea", "identify", "idle", "ignore", "ill", "illegal",
        "illness", "image", "imitate", "immense", "immune", "impact", "impose", "improve",
        "impulse", "inch", "include", "income", "increase", "index", "indicate", "indoor",
        "industry", "infant", "inflict", "inform", "inhale", "inherit", "initial", "inject",
        "injury", "inmate", "inner", "innocent", "input", "inquiry", "insane", "insect",
        "inside", "inspire", "install", "intact", "interest", "into", "invest", "invite",
        "involve", "iron", "island", "isolate", "issue", "item", "ivory", "jacket",
        "jaguar", "jar", "jazz", "jealous", "jeans", "jelly", "jewel", "job",
        "join", "joke", "journey", "joy", "judge", "juice", "jump", "jungle",
        "junior", "junk", "just", "kangaroo", "keen", "keep", "ketchup", "key",
        "kick", "kid", "kidney", "kind", "kingdom", "kiss", "kit", "kitchen",
        "kite", "kitten", "kiwi", "knee", "knife", "knock", "know", "lab",
        "label", "labor", "ladder", "lady", "lake", "lamp", "language", "laptop",
        "large", "later", "latin", "laugh", "laundry", "lava", "law", "lawn",
        "lawsuit", "layer", "lazy", "leader", "leaf", "learn", "leave", "lecture",
        "left", "leg", "legal", "legend", "leisure", "lemon", "lend", "length",
        "lens", "leopard", "lesson", "letter", "level", "liar", "liberty", "library",
        "license", "life", "lift", "light", "like", "limb", "limit", "link",
        "lion", "liquid", "list", "little", "live", "lizard", "load", "loan",
        "lobster", "local", "lock", "logic", "lonely", "long", "loop", "lottery",
        "loud", "lounge", "love", "loyal", "lucky", "luggage", "lumber", "lunar",
        "lunch", "luxury", "lyrics", "machine", "mad", "magic", "magnet", "maid",
        "mail", "main", "major", "make", "mammal", "man", "manage", "mandate",
        "mango", "mansion", "manual", "maple", "marble", "march", "margin", "marine",
        "market", "marriage", "mask", "mass", "master", "match", "material", "math",
        "matrix", "matter", "maximum", "maze", "meadow", "mean", "measure", "meat",
        "mechanic", "medal", "media", "melody", "melt", "member", "memory", "men",
        "mend", "mental", "mentor", "menu", "mercy", "merge", "merit", "merry",
        "mesh", "message", "metal", "method", "middle", "midnight", "milk", "million",
        "mimic", "mind", "minimum", "minor", "minute", "miracle", "mirror", "misery",
        "miss", "mistake", "mix", "mixed", "mixture", "mobile", "model", "modify",
        "mom", "moment", "monitor", "monkey", "monster", "month", "moon", "moral",
        "more", "morning", "mosquito", "mother", "motion", "motor", "mountain", "mouse",
        "move", "movie", "much", "muffin", "mule", "multiply", "muscle", "museum",
        "mushroom", "music", "must", "mutual", "myself", "mystery", "myth", "naive",
        "name", "napkin", "narrow", "nasty", "nation", "nature", "near", "neck",
        "need", "negative", "neglect", "neither", "nephew", "nerve", "nest", "net",
        "network", "neutral", "never", "news", "next", "nice", "night", "noble",
        "noise", "nominee", "noodle", "normal", "north", "nose", "notable", "note",
        "nothing", "notice", "novel", "now", "nuclear", "number", "nurse", "nut",
        "oak", "obey", "object", "oblige", "obscure", "observe", "obtain", "obvious",
        "occur", "ocean", "october", "odor", "off", "offer", "office", "often",
        "oil", "okay", "old", "olive", "olympic", "omit", "once", "one",
        "onion", "online", "only", "open", "opera", "opinion", "oppose", "option",
        "orange", "orbit", "orchard", "order", "ordinary", "organ", "orient", "original",
        "orphan", "ostrich", "other", "outdoor", "outer", "output", "outside", "oval",
        "oven", "over", "own", "owner", "oxygen", "oyster", "ozone", "paddle",
        "page", "pair", "palace", "palm", "panda", "panel", "panic", "panther",
        "paper", "parade", "parent", "park", "parrot", "party", "pass", "patch",
        "path", "patient", "patrol", "pattern", "pause", "pave", "payment", "peace",
        "peanut", "pear", "peasant", "pelican", "pen", "penalty", "pencil", "people",
        "pepper", "perfect", "permit", "person", "pet", "phone", "photo", "phrase",
        "physical", "piano", "picnic", "picture", "piece", "pig", "pigeon", "pill",
        "pilot", "pink", "pioneer", "pipe", "pistol", "pitch", "pizza", "place",
        "planet", "plastic", "plate", "play", "please", "pledge", "pluck", "plug",
        "plunge", "poem", "poet", "point", "polar", "pole", "police", "pond",
        "pony", "pool", "popular", "portion", "position", "possible", "post", "potato",
        "pottery", "poverty", "powder", "power", "practice", "praise", "predict", "prefer",
        "prepare", "present", "pretty", "prevent", "price", "pride", "primary", "print",
        "priority", "prison", "private", "prize", "problem", "process", "produce", "profit",
        "program", "project", "promote", "proof", "property", "prosper", "protect", "proud",
        "provide", "public", "pudding", "pull", "pulp", "pulse", "pumpkin", "punch",
        "pupil", "puppy", "purchase", "purity", "purpose", "purse", "push", "put",
        "puzzle", "pyramid", "quality", "quantum", "quarter", "question", "quick", "quit",
        "quiz", "quote", "rabbit", "raccoon", "race", "rack", "radar", "radio",
        "rail", "rain", "raise", "rally", "ramp", "ranch", "random", "range",
        "rapid", "rare", "rate", "rather", "raven", "raw", "reach", "react",
        "read", "real", "realm", "rear", "reason", "rebel", "rebuild", "recall",
        "receive", "recipe", "record", "recover", "recruit", "reduce", "reflect", "reform",
        "refuse", "region", "regret", "regular", "reject", "relax", "release", "relief",
        "rely", "remain", "remember", "remind", "remote", "remove", "render", "renew",
        "rent", "reopen", "repair", "repeat", "replace", "reply", "report", "represent",
        "reproduce", "public", "request", "require", "rescue", "resemble", "resist", "resource",
        "response", "result", "retire", "retreat", "return", "reunion", "reveal", "review",
        "reward", "rhythm", "rib", "ribbon", "rice", "rich", "ride", "ridge",
        "rifle", "right", "rigid", "ring", "riot", "ripple", "risk", "ritual",
        "rival", "river", "road", "roast", "robot", "robust", "rocket", "romance",
        "roof", "rookie", "room", "root", "rose", "rotate", "rough", "round",
        "route", "royal", "rubber", "rude", "rug", "rule", "run", "runway",
        "rural", "sad", "saddle", "sadness", "safe", "sail", "salad", "salmon",
        "salon", "salt", "salute", "same", "sample", "sand", "satisfy", "satoshi",
        "sauce", "sausage", "save", "say", "scale", "scan", "scare", "scatter",
        "scene", "scent", "scheme", "school", "science", "scissors", "scorpion", "scout",
        "scrap", "screen", "script", "scrub", "sea", "search", "season", "seat",
        "second", "secret", "section", "security", "seed", "seek", "segment", "select",
        "sell", "seminar", "senior", "sense", "sentence", "series", "service", "session",
        "settle", "setup", "seven", "shadow", "shaft", "shallow", "share", "shed",
        "shell", "sheriff", "shield", "shift", "shine", "ship", "shiver", "shock",
        "shoe", "shoot", "shop", "short", "shoulder", "shove", "shrimp", "shrug",
        "shuffle", "shy", "sibling", "sick", "side", "siege", "sight", "sign",
        "silent", "silk", "silly", "silver", "similar", "simple", "since", "sing",
        "siren", "sister", "situate", "six", "size", "skate", "sketch", "ski",
        "skill", "skin", "skirt", "skull", "slab", "slam", "sleep", "slender",
        "slice", "slide", "slight", "slim", "slogan", "slot", "slow", "slush",
        "small", "smart", "smile", "smoke", "smooth", "snack", "snake", "snap",
        "sniff", "snow", "soar", "soccer", "social", "sock", "soda", "sofa",
        "soft", "solar", "soldier", "solid", "solution", "solve", "someone", "song",
        "soon", "sorry", "sort", "soul", "sound", "soup", "source", "south",
        "space", "spare", "spatial", "spawn", "speak", "special", "speed", "spell",
        "spend", "sphere", "spice", "spider", "spike", "spin", "spirit", "split",
        "spoil", "sponsor", "spoon", "sport", "spot", "spray", "spread", "spring",
        "spy", "square", "squeeze", "squirrel", "stable", "stadium", "staff", "stage",
        "stairs", "stamp", "stand", "start", "state", "stay", "steak", "steel",
        "stem", "step", "stereo", "stick", "still", "sting", "stock", "stomach",
        "stone", "stool", "story", "stove", "strategy", "street", "strike", "strong",
        "struggle", "student", "stuff", "stumble", "stun", "stunt", "style", "subject",
        "submit", "subway", "success", "such", "sudden", "suffer", "sugar", "suggest",
        "suit", "summer", "sun", "sunny", "sunset", "super", "supply", "supreme",
        "sure", "surface", "surge", "surprise", "surround", "survey", "suspect", "sustain",
        "swallow", "swamp", "swap", "swarm", "swear", "sweat", "sweep", "sweet",
        "swift", "swim", "swing", "switch", "sword", "symbol", "symptom", "syrup",
        "system", "table", "tackle", "tag", "tail", "talent", "talk", "tank",
        "tape", "target", "task", "taste", "tattoo", "taxi", "teach", "team",
        "tell", "ten", "tenant", "tennis", "tent", "term", "test", "text",
        "thank", "that", "theme", "then", "theory", "there", "they", "thing",
        "this", "thought", "three", "thrive", "throw", "thumb", "thunder", "ticket",
        "tide", "tiger", "tilt", "timber", "time", "tiny", "tip", "tired",
        "tissue", "title", "toast", "tobacco", "toddler", "toe", "together", "toilet",
        "token", "tomato", "tomorrow", "tone", "tongue", "tonight", "tool", "tooth",
        "top", "topic", "topple", "torch", "tornado", "tortoise", "toss", "total",
        "tourist", "toward", "tower", "town", "toy", "track", "trade", "traffic",
        "tragic", "train", "transfer", "trap", "trash", "travel", "tray", "treat",
        "tree", "trend", "trial", "tribe", "trick", "trigger", "trim", "trip",
        "trophy", "trouble", "truck", "true", "truly", "trumpet", "trust", "truth",
        "try", "tube", "tuition", "tumble", "tuna", "tunnel", "turkey", "turn",
        "turtle", "twelve", "twenty", "twice", "twin", "twist", "two", "type",
        "typical", "ugly", "umbrella", "unable", "unaware", "uncle", "uncover", "under",
        "undo", "unfair", "unfold", "unhappy", "uniform", "unique", "unit", "universe",
        "unknown", "unlock", "until", "unusual", "unveil", "update", "upgrade", "uphold",
        "upon", "upper", "upset", "urban", "urge", "usage", "use", "used",
        "useful", "useless", "usual", "utility", "vacant", "vacuum", "vague", "valid",
        "valley", "valve", "van", "vanish", "vapor", "various", "vegan", "velvet",
        "vendor", "venture", "venue", "verb", "verify", "version", "very", "vessel",
        "veteran", "viable", "vibrant", "vicious", "victory", "video", "view", "village",
        "vintage", "violin", "virtual", "virus", "visa", "visit", "visual", "vital",
        "vivid", "vocal", "voice", "void", "volcano", "volume", "vote", "voyage",
        "wage", "wagon", "wait", "walk", "wall", "walnut", "want", "warfare",
        "warm", "warrior", "wash", "wasp", "waste", "water", "wave", "way",
        "wealth", "weapon", "wear", "weasel", "weather", "web", "wedding", "weekend",
        "weird", "welcome", "west", "wet", "whale", "what", "wheat", "wheel",
        "when", "where", "whip", "whisper", "whistle", "white", "who", "whole",
        "whom", "whose", "why", "wide", "width", "wife", "wild", "will",
        "win", "window", "wine", "wing", "wink", "winner", "winter", "wire",
        "wisdom", "wise", "wish", "witness", "wolf", "woman", "wonder", "wood",
        "wool", "word", "work", "world", "worry", "worth", "wrap", "wreck",
        "wrestle", "wrist", "write", "wrong", "yard", "year", "yellow", "you",
        "young", "youth", "zebra", "zero", "zone", "zoo"
    ]
    
    @classmethod
    def generate(cls, word_count: int = 12) -> str:
        """Generate a mnemonic phrase"""
        if word_count not in [12, 15, 18, 21, 24]:
            word_count = 12
        
        entropy_bits = (word_count // 3) * 32
        entropy = secrets.token_bytes(entropy_bits // 8)
        
        # Simple checksum (for real BIP39 would use SHA256)
        checksum = sha256(entropy.hex())[:2]
        
        words = []
        entropy_int = int.from_bytes(entropy, 'big')
        total_bits = entropy_bits + 4
        
        for i in range(word_count):
            idx = (entropy_int >> ((total_bits - 4) - (i * 11))) & 0x7FF
            words.append(cls.WORDLIST[idx % len(cls.WORDLIST)])
        
        return " ".join(words)
    
    @classmethod
    def to_seed(cls, mnemonic: str, password: str = "") -> bytes:
        """Convert mnemonic to seed"""
        # Simplified - real impl would use PBKDF2
        return hashlib.pbkdf2_hmac('sha512', mnemonic.encode(), password.encode(), 2048)


class HDWallet:
    """Hierarchical Deterministic Wallet"""
    
    def __init__(self, seed: bytes = None, mnemonic: str = None, password: str = ""):
        self.master_key = None
        self.chain_code = None
        self.mnemonic = mnemonic
        
        if mnemonic:
            seed = Mnemonic.to_seed(mnemonic, password)
        
        if seed:
            self.master_key = seed[:32]
            self.chain_code = seed[32:64]
    
    def derive_path(self, path: str = "m/44'/118'/0'/0/0") -> tuple:
        """Derive key from path (e.g., m/44'/118'/0'/0/0)"""
        # Simplified derivation
        key = self.master_key.hex()
        for part in path.split('/'):
            if part.startswith('m'):
                continue
            # In real impl, would use HMAC-SHA512
            key = sha256(key + part)
        
        # Generate keypair from derived key
        priv_key = key[:64]
        return priv_key, priv_key  # Simplified
    
    def generate_address(self, index: int = 0, hardened: bool = True) -> str:
        """Generate address at index"""
        path = f"m/44'/118'/0'/{'0' if hardened else 1}/{index}"
        priv, _ = self.derive_path(path)
        # Use priv key to gen address
        return get_address(priv)


# ========== WALLET TYPES ==========
class WalletType:
    """Wallet type constants"""
    HOT = "hot"           # Online, full access
    COLD = "cold"         # Offline, signing only
    WATCHING = "watching" # Read-only
    MULTISIG = "multisig" # Multi-signature
    HARDWARE = "hardware" # Hardware wallet


@dataclass
class WalletAccount:
    """Wallet account with multiple addresses"""
    wallet_id: str
    name: str
    wallet_type: str
    addresses: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "wallet_id": self.wallet_id,
            "name": self.name,
            "type": self.wallet_type,
            "addresses": self.addresses,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "metadata": self.metadata
        }


class WalletManager:
    """Manages multiple wallet accounts"""
    
    def __init__(self, storage_path: str = "wallets.json"):
        self.storage_path = storage_path
        self.wallets: Dict[str, WalletAccount] = {}
        self.load()
    
    def load(self):
        """Load wallets from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for w in data.get("wallets", []):
                    self.wallets[w["wallet_id"]] = WalletAccount(**w)
        except:
            pass
    
    def save(self):
        """Save wallets to storage"""
        data = {"wallets": [w.to_dict() for w in self.wallets.values()]}
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_wallet(self, name: str, wallet_type: str = WalletType.HOT, 
                      mnemonic: str = None) -> WalletAccount:
        """Create a new wallet account"""
        wallet_id = f"wallet_{secrets.token_hex(8)}"
        
        # Generate addresses
        addresses = []
        if wallet_type == WalletType.HOT or wallet_type == WalletType.COLD:
            if mnemonic:
                hd = HDWallet(mnemonic=mnemonic)
                for i in range(5):
                    addr = hd.generate_address(i)
                    addresses.append(addr)
            else:
                for i in range(5):
                    priv, pub = generate_keypair()
                    addr = get_address(pub)
                    addresses.append(addr)
        
        wallet = WalletAccount(
            wallet_id=wallet_id,
            name=name,
            wallet_type=wallet_type,
            addresses=addresses
        )
        
        self.wallets[wallet_id] = wallet
        self.save()
        
        return wallet
    
    def get_wallet(self, wallet_id: str) -> Optional[WalletAccount]:
        """Get wallet by ID"""
        return self.wallets.get(wallet_id)
    
    def add_address(self, wallet_id: str) -> str:
        """Add a new address to wallet"""
        if wallet_id not in self.wallets:
            return None
        
        wallet = self.wallets[wallet_id]
        
        # Generate new address
        priv, pub = generate_keypair()
        addr = get_address(pub)
        
        wallet.addresses.append(addr)
        self.save()
        
        return addr
    
    def import_private_key(self, private_key: str, name: str = "Imported") -> WalletAccount:
        """Import a private key"""
        # Derive address from private key (simplified)
        wallet_id = f"wallet_{secrets.token_hex(8)}"
        
        wallet = WalletAccount(
            wallet_id=wallet_id,
            name=name,
            wallet_type=WalletType.WATCHING,
            addresses=[get_address(private_key)]  # Simplified
        )
        
        self.wallets[wallet_id] = wallet
        self.save()
        
        return wallet
    
    def delete_wallet(self, wallet_id: str) -> bool:
        """Delete a wallet"""
        if wallet_id in self.wallets:
            del self.wallets[wallet_id]
            self.save()
            return True
        return False
    
    def list_wallets(self, wallet_type: str = None) -> List[Dict]:
        """List all wallets"""
        wallets = self.wallets.values()
        if wallet_type:
            wallets = [w for w in wallets if w.wallet_type == wallet_type]
        return [w.to_dict() for w in wallets]


# ========== WALLET CONNECTIVITY ==========
class WalletClient:
    """Client for interacting with blockchain node"""
    
    def __init__(self, node_url: str = MAIN_NODE_URL):
        self.node_url = node_url
    
    def get_balance(self, address: str) -> Dict:
        """Get balance"""
        try:
            resp = requests.get(f"{self.node_url}/balance/{address}", timeout=5)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def send(self, from_addr: str, to_addr: str, amount: float, 
             private_key: str, fee: float = 0.01) -> Dict:
        """Send transaction"""
        try:
            resp = requests.post(
                f"{self.node_url}/wallet/transfer",
                json={
                    "sender": from_addr,
                    "recipient": to_addr,
                    "amount": amount,
                    "private_key": private_key,
                    "fee": fee
                },
                timeout=30
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_history(self, address: str, limit: int = 50) -> List[Dict]:
        """Get transaction history"""
        try:
            resp = requests.get(
                f"{self.node_url}/search",
                params={"sender": address, "limit": limit},
                timeout=10
            )
            return resp.json().get("results", [])
        except:
            return []
    
    def stake(self, address: str, amount: float, private_key: str) -> Dict:
        """Stake tokens"""
        tx = {
            "tx_type": "STAKE",
            "sender": address,
            "amount": amount,
            "fee": 0.01,
            "timestamp": time.time()
        }
        
        from crypto import sign
        tx["signature"] = sign(private_key, json.dumps(tx))
        
        try:
            resp = requests.post(f"{self.node_url}/broadcast", json=tx, timeout=30)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_staking_info(self, address: str) -> Dict:
        """Get staking info"""
        try:
            resp = requests.get(f"{self.node_url}/economics/staking/apr/{address}", timeout=5)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_nfts(self, address: str) -> List[Dict]:
        """Get NFTs owned by address"""
        try:
            resp = requests.get(f"{self.node_url}/nft/owner/{address}", timeout=5)
            return resp.json().get("nfts", [])
        except:
            return []


# ========== WALLET BACKUP/RESTORE ==========
class WalletBackup:
    """Wallet backup and restore"""
    
    @staticmethod
    def export_json(wallet: WalletAccount, private_keys: Dict[str, str]) -> Dict:
        """Export wallet to JSON"""
        return {
            "wallet_id": wallet.wallet_id,
            "name": wallet.name,
            "type": wallet.wallet_type,
            "addresses": wallet.addresses,
            "private_keys": private_keys,  # Map address -> private key
            "created_at": wallet.created_at,
            "version": "1.0"
        }
    
    @staticmethod
    def export_QR(wallet: WalletAccount, private_keys: Dict[str, str]) -> str:
        """Generate QR code data for wallet (simplified)"""
        data = json.dumps(WalletBackup.export_json(wallet, private_keys))
        return data  # In real impl, would generate QR
    
    @staticmethod
    def import_json(data: Dict) -> WalletAccount:
        """Import wallet from JSON"""
        return WalletAccount(
            wallet_id=data.get("wallet_id", f"wallet_{secrets.token_hex(8)}"),
            name=data.get("name", "Imported"),
            wallet_type=data.get("type", WalletType.HOT),
            addresses=data.get("addresses", []),
            created_at=data.get("created_at", time.time())
        )


# ========== TRANSACTION BUILDER ==========
class TransactionBuilder:
    """Build complex transactions"""
    
    def __init__(self, client: WalletClient = None):
        self.client = client or WalletClient()
        self.inputs: List[Dict] = []
        self.outputs: List[Dict] = []
        self.fee = 0.01
    
    def add_input(self, tx_hash: str, index: int, amount: float, address: str):
        """Add input to transaction"""
        self.inputs.append({
            "tx_hash": tx_hash,
            "index": index,
            "amount": amount,
            "address": address
        })
    
    def add_output(self, address: str, amount: float):
        """Add output to transaction"""
        self.outputs.append({
            "address": address,
            "amount": amount
        })
    
    def set_fee(self, fee: float):
        """Set transaction fee"""
        self.fee = fee
    
    def build(self) -> Dict:
        """Build transaction dict"""
        total_in = sum(i["amount"] for i in self.inputs)
        total_out = sum(o["amount"] for o in self.outputs)
        
        return {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "fee": self.fee,
            "total_in": total_in,
            "total_out": total_out,
            "change": total_in - total_out - self.fee
        }
    
    def broadcast(self, sender: str, private_key: str) -> Dict:
        """Broadcast the transaction"""
        # Build simple transfer for now
        tx = self.outputs[0] if self.outputs else {}
        return self.client.send(
            sender, 
            tx.get("address", ""), 
            tx.get("amount", 0), 
            private_key,
            self.fee
        )


# ========== WALLET GUI DATA ==========
class WalletUI:
    """Generate wallet UI data"""
    
    @staticmethod
    def dashboard(wallet: WalletAccount, client: WalletClient) -> Dict:
        """Generate dashboard data"""
        total_balance = 0
        total_staked = 0
        nfts = []
        
        for addr in wallet.addresses:
            bal = client.get_balance(addr)
            total_balance += bal.get("balance", 0)
            total_staked += bal.get("staked", 0)
            nfts.extend(client.get_nfts(addr))
        
        return {
            "wallet_id": wallet.wallet_id,
            "name": wallet.name,
            "type": wallet.wallet_type,
            "balance": total_balance,
            "staked": total_staked,
            "total": total_balance + total_staked,
            "address_count": len(wallet.addresses),
            "nft_count": len(nfts),
            "primary_address": wallet.addresses[0] if wallet.addresses else None
        }
    
    @staticmethod
    def address_list(wallet: WalletAccount) -> List[Dict]:
        """List all addresses with QR data"""
        return [
            {
                "address": addr,
                "index": i,
                "qr_data": f"calicos:{addr}"  # URI scheme
            }
            for i, addr in enumerate(wallet.addresses)
        ]