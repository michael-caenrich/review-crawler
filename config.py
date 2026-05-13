"""Store input, output file paths, negative keywords, selectors, product IDs for JD and Taobao platforms."""

import pathlib

CDP_URL = "http://127.0.0.1:9222"

BASE_DIR = pathlib.Path(__file__).resolve().parent

NEGATIVE_KEYWORDS = [
    # Safety hazards
    "皮肤刺激", "眼睛刺激", "过敏", "疙瘩", "痘", "受伤", "发烫", "危险", "刺鼻",
    # Product defects
    "假货", "破损", "坏了", "少配件", "空的", "二手", "没有电池",
    # Quality
    "质量差", "质量一般", "垃圾", "廉价", "不推荐",
    # Usability
    "不好用", "难用", "充不满", "不好",
    # Returns & service
    "退货", "退款", "失望",
]

# JD setup
JD_DATA_PATH = BASE_DIR / "data" / "jd_reviews_raw.xlsx"
JD_OUTPUT_PATH = BASE_DIR / "output" / "jd_results.xlsx"

JD_SELECTORS = {
    "全部评价": ["#comment-root > div.all-btn > div", "text=全部评价"], # #nav-review > div > button
    "差评": ["#rateList span:has-text('差评')", "text=差评"],
    "中评": ["#rateList span:has-text('中评')", "text=中评"],
    "review_card": ".jdc-pc-rate-card",
    "review_text": ".jdc-pc-rate-card-main-desc",
}

JD_PRODUCT_IDS = [
    # 玩具
    100112573693,
    100011166107,
    100190960941,
    # # 儿童护肤
    100014327793,
    100331533320,
    10151921151284,
    # 童装
    100320215916,
    10153675447623,
    100240028873,
    # 充电器
    100043899267,
    100266373302,
    100251221945,
]

# Taobao setup
TAOBAO_DATA_PATH = BASE_DIR / "data" / "taobao_reviews_raw.xlsx"
TAOBAO_OUTPUT_PATH = BASE_DIR / "output" / "taobao_results.xlsx"

TAOBAO_SELECTORS = {
    "查看全部评价": [".footer--gVLORU06 > div", "text=查看全部评价"],
    "review_card": ".Comment--H5QmJwe9",
    "review_text": ".content--uonoOhaz",
}

TAOBAO_PRODUCT_IDS = [
    # 玩具
    1025853085451,
    696791403725,
    987359046806,
    # 儿童护肤
    1019878723701,
    962108711151,
    901039506585,
    # 童装
    932590730362,
    836860921639,
    737445350142,
]

NEGATIVE_KEYWORDS_EN = [
    # Safety hazards
    "irritat", "allerg", "rash", "burn", "dangerous", "hazard", "toxic", "chok",
    # Product defects
    "fake", "broken", "damaged", "missing", "empty", "defect", "counterfeit",
    # Quality
    "poor quality", "bad quality", "cheap", "garbage", "trash", "terrible", "worst",
    # Usability
    "doesn't work", "does not work", "not working", "useless", "difficult to use",
    # Returns & service
    "refund", "return", "disappointed", "scam", "waste of money",
]

# AliExpress setup
ALIEXPRESS_DATA_PATH = BASE_DIR / "data" / "aliexpress_reviews_raw.xlsx"
ALIEXPRESS_OUTPUT_PATH = BASE_DIR / "output" / "aliexpress_results.xlsx"

ALIEXPRESS_SELECTORS = {
    "view_more": "#nav-review button[class*=v3--btn]",
    "ratings_dropdown": ".comet-v2-modal-content [class*=filterItem]:first-child button",
    "1_star": "li:has-text('1 Star')",
    "2_star": "li:has-text('2 Star')",
    "review_container": ".comet-v2-modal-content [class*=itemContent]",
    "review_text": ".comet-v2-modal-content [class*=itemReview]",
}

ALIEXPRESS_PRODUCT_IDS = [
    # 玩具
    3256805966506572,
    3256806737170819,
    3256807549555704,
    3256811437942379,
    # 爱护儿童品
    3256809812110929,
    3256809965931098,
    # 童装
    3256805861450624,
    3256808427397420,
    3256806767440010,
]