def build_sqlite_db(conn, cur):
    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_genre" (
  "linkid" CHAR(16) NOT NULL,
  "name" TEXT,
  "title" TEXT,
  PRIMARY KEY ("linkid")
);
    ''')

    cur.execute('''
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
    ''')

    cur.execute('''
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
    ''')
    cur.execute('''
CREATE TABLE IF NOT EXISTS "av_extend" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "extend_name" VARCHAR(10) NOT NULL,
  "key" VARCHAR(20) NOT NULL,
  "val" TEXT NOT NULL
);
    ''')

    conn.commit()
