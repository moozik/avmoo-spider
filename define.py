# 表名
AV_STARS = 'av_stars'
AV_GENRE = 'av_genre'
AV_LIST = 'av_list'
AV_EXTEND = 'av_extend'

# 右上角切换语言
COUNTRY_MAP = {
    'en': 'English',
    'ja': '日本语',
    'tw': '正體中文',
    'cn': '简体中文',
}

PAGE_TYPE_MAP = {
    # page_type名
    'director': {
        # 页面名称
        'name': '导演',
        # 是否允许收藏
        'like_enable': False,
        # 是否允许改显示名称
        'rename_enable': True,
        # db字段, like key
        'key': 'director_url',
        # av_list影片列表查询条件
        'where': "director_url='{}'",
    },
    'movie': {
        'name': '影片',
        'like_enable': True,
        'rename_enable': False,
        'key': 'av_id',
        'where': "linkid='{0}' OR av_id = '{0}'",
    },
    'studio': {
        'name': '制作商',
        'like_enable': True,
        'rename_enable': True,
        'key': 'studio_url',
        'where': "studio_url='{}'",
    },
    'label': {
        'name': '发行商',
        'like_enable': True,
        'rename_enable': True,
        'key': 'label_url',
        'where': "label_url='{}'",
    },
    'series': {
        'name': '系列',
        'like_enable': True,
        'rename_enable': True,
        'key': 'series_url',
        'where': "series_url='{}'",
    },
    'star': {
        'name': '演员',
        'like_enable': False,
        'rename_enable': True,
        'key': 'stars_url',
        'where': "stars_url GLOB '*|{}*'",
    },
    'genre': {
        'name': '分类',
        'like_enable': False,
        'rename_enable': True,
        'key': 'genre_url',
        'where': "genre GLOB '*|{}|*'",
    },
    'group': {
        'name': '番号',
        'like_enable': True,
        'rename_enable': False,
        'key': 'group',
        'where': "av_id LIKE '{}-%'",
    },
    'like': {
        'name': '收藏',
        'like_enable': False,
        'rename_enable': False,
    },
}

# sqlite escapt list
ESCAPE_LIST = (
    ("/", "//"),
    ("'", "''"),
    ("[", "/["),
    ("]", "/]"),
    ("%", "/%"),
    ("&", "/&"),
    ("_", "/_"),
    ("(", "/("),
    (")", "/)"),
)

PAGE_MAX = 100

LOCAL_IP = "127.0.0.1"

# /config
CONFIG_NAME_LIST = [
    "base.avmoo_site",
    "base.db_file",
    "base.port",
    "base.debug_mode",
    "base.readonly",
    "base.country",

    "spider.sleep",
    "spider.insert_threshold",
    "spider.continued_skip_limit",
    "spider.minimum_movie_duration",

    "requests.timeout",
    "requests.user_agent",

    "website.cdn",
    "website.page_limit",
    "website.actresses_page_limit",
    "website.group_page_limit",
    "website.spider_page_interval_timeout",
    "website.search_url",

    "website.group_page_order_by",
    "website.use_cache",
    "website.auto_open_site_on_run",
    "website.auto_open_link_when_crawl_done",
    "website.efficiency_mode",
]

# /spider 文件类型与判定
FILE_TAIL = {
    'mp4': "\\.(mp4|mkv|flv|avi|rm|rmvb|mpg|mpeg|mpe|m1v|mov|3gp|m4v|m3p|wmv|wmp|wm)$",
    'jpg': "\\.(jpg|png|gif|jpeg|bmp|ico)$",
    'mp3': "\\.(mp3|wav|wmv|mpa|mp2|ogg|m4a|aac)$",
    'torrent': "\\.torrent$",
    'zip': "\\.(zip|rar|gz|7z)$",
    'doc': "\\.(xls|xlsx|doc|docx|ppt|pptx|csv|pdf|html|txt)$",
}

# /spider av视频文件判断正则
AV_FILE_REG = "[a-zA-Z]{3,5}-\\d{3,4}"

CREATE_AV_GENRE_SQL = '''
CREATE TABLE IF NOT EXISTS "av_genre" (
  "linkid" CHAR(16) NOT NULL,
  "name" TEXT,
  "title" TEXT,
  PRIMARY KEY ("linkid")
);
'''

CREATE_AV_LIST_SQL = '''
CREATE TABLE IF NOT EXISTS "av_list" (
  "linkid" CHAR(16) NOT NULL,
  "title" TEXT,
  "av_id" VARCHAR(20),
  "release_date" CHAR(10),
  "len" INTEGER,
  "director" TEXT,
  "studio" TEXT,
  "label" TEXT,
  "series" TEXT,
  "genre" TEXT,
  "stars" TEXT,
  "director_url" TEXT,
  "studio_url" CHAR(16),
  "label_url" CHAR(16),
  "series_url" TEXT,
  "stars_url" TEXT,
  "bigimage" TEXT,
  "image_len" INTEGER,
  PRIMARY KEY ("linkid")
);
    '''

CREATE_AV_STARS_SQL = '''
CREATE TABLE IF NOT EXISTS "av_stars" (
  "linkid" CHAR(16) NOT NULL,
  "name" TEXT,
  "name_history" TEXT,
  "birthday" TEXT,
  "height" TEXT,
  "cup" CHAR(1),
  "bust" TEXT,
  "waist" TEXT,
  "hips" TEXT,
  "hometown" TEXT,
  "hobby" TEXT,
  "headimg" TEXT,
  PRIMARY KEY ("linkid")
);
'''

CREATE_AV_EXTEND_SQL = '''
CREATE TABLE IF NOT EXISTS "av_extend" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "extend_name" VARCHAR(10) NOT NULL,
  "key" VARCHAR(20) NOT NULL,
  "val" TEXT NOT NULL
);
'''

AV_GENRE_DEMO_DATA = [
    ('like', 'group', 'SSIS'),
    ('like', 'studio_url', '80be243ea6164094'),
    ('like', 'label_url', 'b0b3be30e6bf490f'),
    ('like', 'series_url', 'c343a1499f108277'),
    ('like', 'av_id', 'SSIS-318'),
    ('like', 'av_id', 'SSIS-318'),
    ('movie_res', 'SSIS-318', 'magnet:?xt=urn:btih:E0C7B27071A832388AF9C54553EECF71F4094256&dn=SSIS-318-C'),
]
