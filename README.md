## 运行需求
python3
**第三方包**
```
pip install requests
pip install lxml
pip install flask
```

## 使用方法

### 1)
`python flask_avmo.py` 启动本地web(首次打开会创建db)
打开`http://127.0.0.1:5000`

### 2)
抓取指定演员所有影片

举例链接`https://avmoo.casa/cn/star/1971f1973cf8172f`

将`1971f1973cf8172f`放到本地web的搜索框，可以更新指定演员id的所有影片到本地数据库
