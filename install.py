def buildSqliteDb(conn, cur):
    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_genre" (
  "linkid" TEXT(16) NOT NULL,
  "name" TEXT,
  "title" TEXT,
  PRIMARY KEY ("linkid")
);
    ''')

    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_like" (
  "type" TEXT(20) NOT NULL,
  "val" TEXT(300) NOT NULL,
  "time" TEXT(50),
  PRIMARY KEY ("type", "val")
);
    ''')

    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_list" (
  "linkid" TEXT(16) NOT NULL,
  "title" TEXT(500),
  "av_id" TEXT(50),
  "release_date" TEXT(20),
  "len" TEXT(20),
  "director" TEXT(100),
  "studio" TEXT(100),
  "label" TEXT(100),
  "series" TEXT(200),
  "genre" TEXT(200),
  "stars" TEXT(300),
  "director_url" TEXT(10),
  "studio_url" TEXT(10),
  "label_url" TEXT(10),
  "series_url" TEXT(10),
  "stars_url" TEXT(500),
  "bigimage" TEXT(200),
  "image_len" INTEGER,
  PRIMARY KEY ("linkid")
);
    ''')

    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_stars" (
  "linkid" TEXT(16) NOT NULL,
  "name" TEXT(50),
  "name_history" TEXT(50),
  "birthday" TEXT(12),
  "height" TEXT(10),
  "cup" TEXT(10),
  "bust" TEXT(10),
  "waist" TEXT(10),
  "hips" TEXT(10),
  "hometown" TEXT(50),
  "hobby" TEXT(50),
  "headimg" TEXT(200),
  PRIMARY KEY ("linkid")
);
    ''')
    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_extend" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "extend_name" TEXT(20) NOT NULL,
  "key" TEXT(20) NOT NULL,
  "val" TEXT(500) NOT NULL
);
    ''')

    conn.commit()
