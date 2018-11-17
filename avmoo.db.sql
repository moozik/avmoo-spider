/*
Navicat SQLite Data Transfer

Source Server         : avmoo
Source Server Version : 30714
Source Host           : :0

Target Server Type    : SQLite
Target Server Version : 30714
File Encoding         : 65001

Date: 2018-11-18 00:28:27
*/

PRAGMA foreign_keys = OFF;

-- ----------------------------
-- Table structure for av_163sub
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_163sub";
CREATE TABLE "av_163sub" (
"sub_id"  TEXT NOT NULL,
"av_id"  TEXT,
"sub_time"  TEXT(20),
PRIMARY KEY ("sub_id" ASC)
);

-- ----------------------------
-- Table structure for av_163sub_log
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_163sub_log";
CREATE TABLE "av_163sub_log" (
"id"  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
"sub_keyword"  TEXT,
"run_time"  TEXT,
"data_count"  INTEGER,
"insert_count"  INTEGER
);

-- ----------------------------
-- Table structure for av_error_linkid
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_error_linkid";
CREATE TABLE "av_error_linkid" (
"id"  INTEGER PRIMARY KEY AUTOINCREMENT,
"linkid"  TEXT(4) NOT NULL,
"status_code"  INTEGER,
"datetime"  TEXT(50)
);

-- ----------------------------
-- Table structure for av_genre
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_genre";
CREATE TABLE "av_genre" (
"id"  TEXT NOT NULL,
"name"  TEXT,
"title"  TEXT,
PRIMARY KEY ("id")
);

-- ----------------------------
-- Table structure for av_like
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_like";
CREATE TABLE "av_like" (
"type"  TEXT(20) NOT NULL,
"val"  TEXT(300) NOT NULL,
"time"  TEXT(50),
PRIMARY KEY ("type" ASC, "val" ASC)
);

-- ----------------------------
-- Table structure for av_list
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_list";
CREATE TABLE "av_list" (
"id"  INTEGER,
"linkid"  TEXT(10) NOT NULL,
"title"  TEXT(500),
"av_id"  TEXT(50),
"release_date"  TEXT(20),
"len"  TEXT(20),
"director"  TEXT(100),
"studio"  TEXT(100),
"label"  TEXT(100),
"series"  TEXT(200),
"genre"  TEXT(200),
"stars"  TEXT(300),
"director_url"  TEXT(10),
"studio_url"  TEXT(10),
"label_url"  TEXT(10),
"series_url"  TEXT(10),
"stars_url"  TEXT(300),
"bigimage"  TEXT(200),
"image_len"  INTEGER,
PRIMARY KEY ("linkid" ASC)
);

-- ----------------------------
-- Table structure for av_stars
-- ----------------------------
DROP TABLE IF EXISTS "main"."av_stars";
CREATE TABLE "av_stars" (
"id"  INTEGER NOT NULL,
"linkid"  TEXT(4),
"name"  TEXT(50),
"name_history"  TEXT(50),
"birthday"  TEXT(12),
"height"  TEXT(10),
"cup"  TEXT(10),
"bust"  TEXT(10),
"waist"  TEXT(10),
"hips"  TEXT(10),
"hometown"  TEXT(50),
"hobby"  TEXT(50),
"headimg"  TEXT(200),
PRIMARY KEY ("id" ASC)
);

-- ----------------------------
-- Table structure for sqlite_sequence
-- ----------------------------
DROP TABLE IF EXISTS "main"."sqlite_sequence";
CREATE TABLE sqlite_sequence(name,seq);

-- ----------------------------
-- Indexes structure for table av_list
-- ----------------------------
CREATE INDEX "main"."av_list__av_id_DESC"
ON "av_list" ("av_id" DESC);
CREATE INDEX "main"."av_list__id_DESC"
ON "av_list" ("id" DESC);
