CREATE TABLE `av_list` (
  `id` int(10) NOT NULL AUTO_INCREMENT,
  `linkid` varchar(10) DEFAULT NULL COMMENT '链接地址',
  `title` varchar(500) DEFAULT NULL COMMENT '标题',
  `av_id` varchar(50) DEFAULT NULL COMMENT '番号',
  `release_date` varchar(20) DEFAULT NULL COMMENT '发行时间',
  `len` varchar(20) DEFAULT NULL COMMENT '影片长度',
  `director` varchar(100) DEFAULT NULL COMMENT '导演',
  `studio` varchar(100) DEFAULT NULL COMMENT '制作方',
  `label` varchar(100) DEFAULT NULL COMMENT '发行方',
  `series` varchar(200) DEFAULT NULL COMMENT '系列',
  `genre` varchar(200) DEFAULT NULL COMMENT '标签',
  `stars` varchar(300) DEFAULT NULL COMMENT '演员',
  `director_url` varchar(100) DEFAULT NULL COMMENT '导演url',
  `studio_url` varchar(100) DEFAULT NULL COMMENT '制作方url',
  `label_url` varchar(100) DEFAULT NULL COMMENT '发行方url',
  `series_url` varchar(100) DEFAULT NULL COMMENT '系列url',
  `bigimage` varchar(200) DEFAULT NULL COMMENT '封面',
  `image_len` int(10) DEFAULT NULL COMMENT '图片个数',
  PRIMARY KEY (`linkid`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8;
 
CREATE TABLE `av_error_linkid` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `linkid` varchar(4) DEFAULT NULL,
  `status_code` int(5) DEFAULT NULL COMMENT '状态码',
  `datetime` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8;