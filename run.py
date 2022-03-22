import common
import spider
import website
import sys

# 配置初始化
# 1. 读取配置
# 2. 初始化db
# 3. 建表
config_file = None
if len(sys.argv) > 1:
    config_file = sys.argv[1]
common.init(config_file)

# 爬虫类初始化
# 1. 初始化db
# 2. 初始化requests
# 3. genre为空则获取
# 4. 启动爬虫线程
spider.Spider().run()

# flask应用
website.run()
