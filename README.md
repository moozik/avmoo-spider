## 运行需求
python3
**第三方包**
```bash
pip install requests
pip install lxml
pip install flask
```
## 页面功能

- `http://127.0.0.1:5000/` 首页
- `http://127.0.0.1:5000/search/已发布` 已发布
- `http://127.0.0.1:5000/search/已下载` 已下载
- `http://127.0.0.1:5000/search/有资源` 有资源

### 列表页
- `http://127.0.0.1:5000/group` 番号列表
- `http://127.0.0.1:5000/actresses` 演员列表
- `http://127.0.0.1:5000/genre` 类别列表
- `http://127.0.0.1:5000/studio` 制作商列表
- `http://127.0.0.1:5000/label` 发行商列表
- `http://127.0.0.1:5000/series` 系列列表

### 明细页
- `http://127.0.0.1:5000/movie/e3dedf889e44cee8` 影片明细
- `http://127.0.0.1:5000/group/IPX` 番号明细
- `http://127.0.0.1:5000/star/1971f1973cf8172f` 演员明细
- `http://127.0.0.1:5000/genre/dd21aefe7ae3228c` 类别明细
- `http://127.0.0.1:5000/studio/80be243ea6164094` 制作商明细
- `http://127.0.0.1:5000/label/b0b3be30e6bf490f` 发行商明细
- `http://127.0.0.1:5000/series/c28ffa16eae1bf1e` 系列明细
- `http://127.0.0.1:5000/director/bb914a54dc51b21b` 导演明细

### 收藏页
- `http://127.0.0.1:5000/like/group` 收藏番号
- `http://127.0.0.1:5000/like/movie` 收藏影片
- `http://127.0.0.1:5000/like/studio` 收藏制作商
- `http://127.0.0.1:5000/like/label` 收藏发行商
- `http://127.0.0.1:5000/like/series` 收藏系列

### 分析页
- `http://127.0.0.1:5000/analyse/group/IPX` 分析番号
- `http://127.0.0.1:5000/analyse/star/1971f1973cf8172f` 分析演员
- `http://127.0.0.1:5000/analyse/genre/dd21aefe7ae3228c` 分析类别
- `http://127.0.0.1:5000/analyse/studio/80be243ea6164094` 分析制作商
- `http://127.0.0.1:5000/analyse/label/b0b3be30e6bf490f` 分析发行商
- `http://127.0.0.1:5000/analyse/director/bb914a54dc51b21b` 分析导演

### 功能页
- `http://127.0.0.1:5000/spider` 爬虫,输入链接,抓取链接内所有影片
- `http://127.0.0.1:5000/scandisk` 扫描硬盘,扫描本地硬盘,识别番号文件名
- `http://127.0.0.1:5000/config` 修改配置

## 注意事项
1. 右上角的语言切换是用来切换目标站的语言的,会影响演员名/类目名,仿站没有做多语言
2. avmoo最多只支持抓取到100页，超过100页无法抓取
3. 图片卡的时候尝试去`config`页面切换`图片cdn源`
4. 右上角的`链接`按钮指的是avmoo源站对应的链接
5. 爬虫页可以查看最近写入库中的影片，也可以操作爬虫
6. 磁力搜索网站可以自己在配置添加,会在末尾拼av_id

## 打开方法
命令行运行`python run.py`启动本地web(首次打开会跳转到安装页面)
指定配置文件运行`python run.py config_main.db`
默认地址为`http://127.0.0.1:5000`，端口可通过配置修改
