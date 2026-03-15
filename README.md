# weibo 爬虫

> **免责声明：本项目仅供学习交流使用，严禁用于任何非法用途。使用者需遵守相关法律法规及微博平台的服务条款，因违规使用产生的一切后果由使用者自行承担。**

自动爬取某个微博博主转发的微博，根据关键词匹配，记录匹配到的微博的图片，并通过 RabbitMQ 推送到下游处理。

## 快速开始

```bash
git clone --recurse-submodules <repo-url>
cd awsl-weibo-crawler
cp .env.example .env
# 编辑 .env 填入配置
```

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python3 main.py
```

## 配置

| 变量 | 必填 | 说明 |
|------|------|------|
| `awsl_api_url` | 是 | AWSL API 地址，用于动态获取请求 Headers |
| `awsl_api_token` | 是 | AWSL API Bearer Token |
| `db_url` | 是 | MySQL 连接串，如 `mysql+mysqlconnector://user:pass@host/db` |
| `pika_url` | 否 | RabbitMQ 连接串，为空则禁用消息推送 |
| `bot_queue` | 否 | RabbitMQ 队列名 |
| `max_page` | 否 | 每个用户最大爬取页数，默认 50 |

## Docker

推送 semver tag 会自动构建并发布到 GHCR：

```bash
git tag 1.0.0 && git push origin 1.0.0
```
