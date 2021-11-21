## 运行需求
python3
**第三方包**
```
pip install requests
pip install lxml
pip install flask
```
## 功能

### 爬虫
- 打开`http://127.0.0.1:5000/actresses`添加演员id，查询名下所有影片
- 举例:`https://avmoo.casa/cn/star/1971f1973cf8172f`，演员id为`1971f1973cf8172f`

### 仿站

- 多关键字搜索
- 影片收藏管理
- 本地视频路径绑定到番号，在网页中点击打开本地视频
- 扫描本地硬盘视频文件

方便管理影片信息和视频文件

## 打开方法
命令行运行`python flask_avmo.py`或者`start_web.bat` 启动本地web(首次打开会创建db)
打开`http://127.0.0.1:5000`即可看到主页