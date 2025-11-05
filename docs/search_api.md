
## vendors

### bocha web search

example 

```
curl --location 'https://api.bochaai.com/v1/web-search' \
--header 'Authorization: Bearer BOCHA-API-KEY' \
--header 'Content-Type: application/json' \
--data '{
    "query":"阿里巴巴2024年的ESG报告",
    "summary": true,
    "freshness":"noLimit",
    "count": 10
}'
```

response format

```
{"code":200,"log_id":"5cc4ea524eac0d82","msg":null,"data":{"_type":"SearchResponse","queryContext":{"originalQuery":"阿里巴巴2024年的ESG报告"},"webPages":{"webSearchUrl":"https://bochaai.com/search?q=阿里巴巴2024年的ESG报告","totalEstimatedMatches":10000000,"value":[{"id":"https://api.bochaai.com/v1/#WebPages.0","name":"阿里巴巴：2024年环境、社会和治理（ESG）报告（英文版）.pdf","url":"https://m.waitang.com/report/85234526.html","displayUrl":"https://m.waitang.com/report/85234526.html","snippet":"阿里巴巴:2024年环境、社会和治理(ESG)报告(英文版).pdf 智库VIP会员,享80万+报告、方案和资料 开通会员 70 MB,200 页,发布者:wx*ce,发布于2024-07-24 加载","summary":"阿里巴巴:2024年环境、社会和治理(ESG)报告(英文版).pdf 智库VIP会员,享80万+报告、方案和资料 开通会员 70 MB,200 页,发布者:wx*ce,发布于2024-07-24 加载中. 本文档是收费阅读文档,免费内容已阅读结束 阅读完整文档所需金币:20 充值并购买 相关精品文档 pdf 国际清洁交通委员会:2024年道路货运电动化之路:陕西省榆林市49吨纯电半挂牵引车案例报告 pdf 欧洲环境署:2024年欧洲气候风险评估报告(英文版) pdf AIGCC:气候行动100+:2024年净零排放公司基准2.1白皮书(英文版) pdf 国海证券:阿里巴巴W(9988.HK)深度报告:用户为先、AI驱动、战略调整后重启增长 pdf 益海嘉里金龙鱼:2050净零目标及路线图 pdf IPE公众环境研究中心:2024年1-12月城市空气质量简报 pdf IPE公众环境研究中心:2024年12月城市空气质量简报 pdf 普华永道&AIGCC:2024年临界点上的大自然报告(英文版) pdf 清华大学碳中和研究院...","siteName":"外唐智库","siteIcon":"https://th.bochaai.com/favicon?domain_url=https://m.waitang.com/report/85234526.html","datePublished":"2024-07-24T08:00:00+08:00","dateLastCrawled":"2024-07-24T08:00:00Z","cachedPageUrl":null,"language":null,"isFamilyFriendly":null,"isNavigational":null},{"id":"https://api.bochaai.com/v1/#WebPages.1","name":"2024年环境、社会和治理(ESG)报告","url":"https://m.sohu.com/a/800295916_121112996/?pvid=000115_3w_a","displayUrl":"https://m.sohu.com/a/800295916_121112996/?pvid=000115_3w_a","snippet":"公众号 『 碳中和报告之家 』  获取完整报告\n报告共186页\n导读: 报告强调了集团的使命——“让天下没有难做的生意”,并通过技术创新和平台能力支持中小微企业的发展。阿里巴巴致力于构建一个包容、可持","summary":"公众号 『 碳中和报告之家 』  获取完整报告\n报告共186页\n导读: 报告强调了集团的使命——“让天下没有难做的生意”,并通过技术创新和平台能力支持中小微企业的发展。阿里巴巴致力于构建一个包容、可持续的商业生态系统,推动社会和环境的和谐共生。在环境方面,阿里巴巴提出了实现碳中和的目标,并在2024财年取得了显著进展。通过提高清洁能源使用比例和优化数据中心能效,集团成功降低了自身运营的温室气体排放。同时,阿里巴巴通过其平台推动了更广泛的生态减排,助力消费者和企业实现低碳转型。阿里巴巴的2024年ESG报告体现了其作为全球领先企业的责任感,通过实际行动为社会和环境的可持续发展作出了积极贡献。","siteName":"手机搜狐网","siteIcon":"https://th.bochaai.com/favicon?domain_url=https://m.sohu.com/a/800295916_121112996/?pvid=000115_3w_a","datePublished":"2024-08-12T23:57:00+08:00","dateLastCrawled":"2024-08-12T23:57:00Z","cachedPageUrl":null,"language":null,"isFamilyFriendly":null,"isNavigational":null}],"someResultsRemoved":true},"images":{"id":null,"readLink":null,"webSearchUrl":null,"value":[{"webSearchUrl":null,"name":null,"thumbnailUrl":"http://q2.itc.cn/images01/20240812/dc5557e984144ce9a7a69b55bf17a1bb.png","datePublished":null,"contentUrl":"http://q2.itc.cn/images01/20240812/dc5557e984144ce9a7a69b55bf17a1bb.png","hostPageUrl":"https://m.sohu.com/a/800295916_121112996/?pvid=000115_3w_a","contentSize":null,"encodingFormat":null,"hostPageDisplayUrl":"https://m.sohu.com/a/800295916_121112996/?pvid=000115_3w_a","width":0,"height":0,"thumbnail":null}],"isFamilyFriendly":null},"videos":null}}
```

### bocha reranker

curl example
```

curl --location 'https://api.bochaai.com/v1/rerank' \
--header 'Authorization: Bearer BOCHA-API-KEY' \
--header 'Content-Type: application/json' \
--data '{
    "model": "gte-rerank",
    "query": "阿里巴巴2024年的ESG报告",
    "top_n": 2,
    "return_documents": true,
    "documents": [
      "阿里巴巴集团发布《2024财年环境、社会和治理（ESG）报告》（下称“报告”），详细分享过去一年在 ESG各方面取得的进展。 报告显示，阿里巴巴扎实推进减碳举措...",
      "ESG的核心是围绕如何..."
      ]
  }'
```
