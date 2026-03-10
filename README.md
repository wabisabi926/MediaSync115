# MediaSync115

MediaSync115 是一个面向影视资源管理的全栈项目，提供搜索、榜单探索、订阅、转存、115 网盘管理、Emby 联动和任务日志能力。

项目当前采用：
- 前端：Vue 3 + Vite + Element Plus
- 后端：FastAPI + SQLAlchemy + SQLite
- 运行方式：本地开发脚本、Docker、Nginx

## 核心功能

- 影视搜索
  - TMDB 搜索
  - 豆瓣榜单探索
  - TMDB 榜单探索
- 资源获取
  - 115 网盘资源
  - 磁力链接
  - ED2K
  - 支持 Nullbr、Pansou、HDHive、Telegram、SeedHub 等来源
- 转存能力
  - 详情页一键转存
  - 剧集选集转存
  - 探索页转存队列
  - 订阅扫描自动转存
- 订阅能力
  - 电影 / 剧集订阅
  - 订阅扫描
  - 自动清理已完成订阅
- Emby 联动
  - 影视已入库对号标识
  - 剧集缺集判断
  - Emby 全量同步索引
- 系统能力
  - 运行时设置
  - 任务调度
  - 操作日志
  - 健康检查

## 目录结构

```text
MediaSync115/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/            # 路由
│   │   ├── core/           # 配置、数据库
│   │   ├── models/         # ORM 模型
│   │   └── services/       # 业务服务
│   ├── data/               # SQLite 与运行时配置
│   ├── tests/              # 后端测试
│   ├── main.py             # 应用入口
│   └── requirements.txt
├── frontend/               # Vue 前端
│   ├── src/
│   │   ├── api/
│   │   ├── router/
│   │   ├── components/
│   │   └── views/
│   ├── tests/smoke/        # Playwright 冒烟测试
│   └── package.json
├── dev-linux.sh            # Linux 开发启动/重启脚本
└── README.md
```

## 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+
- Linux / WSL / Docker 环境

可选依赖：
- 115 账号 Cookie
- TMDB API Key
- Nullbr 配置
- HDHive Cookie
- Telegram API 凭据
- Emby URL 和 API Key

## 后端环境变量

后端配置模板位于：
- [backend/.env.example](/mnt/d/code/MediaSync115/backend/.env.example)

初始化方式：

```bash
cd backend
cp .env.example .env
```

常用配置项：

- `NULLBR_APP_ID`
- `NULLBR_API_KEY`
- `NULLBR_BASE_URL`
- `TMDB_API_KEY`
- `PAN115_COOKIE`
- `PANSOU_BASE_URL`
- `HDHIVE_COOKIE`
- `HDHIVE_BASE_URL`
- `TG_API_ID`
- `TG_API_HASH`
- `TG_PHONE`
- `EMBY_URL`
- `EMBY_API_KEY`
- `DATABASE_URL`

## 本地开发启动

### 方式一：使用项目脚本

推荐直接使用：

```bash
./dev-linux.sh start
./dev-linux.sh status
./dev-linux.sh restart
./dev-linux.sh stop
./dev-linux.sh logs
```

脚本位置：
- [dev-linux.sh](/mnt/d/code/MediaSync115/dev-linux.sh)

默认端口：
- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`

### 方式二：分别启动前后端

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## Docker

如果仓库中存在 `docker-compose.yml`，可直接使用：

```bash
docker-compose up --build
docker-compose down
```

## 数据与运行时文件

后端运行时数据默认位于：

- `backend/data/mediasync.db`
- `backend/data/runtime_settings.json`

说明：
- `runtime_settings.json` 保存大量运行时设置
- SQLite 数据库存放订阅、日志、任务等数据

## 测试

### 前端构建检查

```bash
cd frontend
npm run build
```

### 前端 Playwright 冒烟测试

已接入最小页面级 smoke：

```bash
cd frontend
npm run test:smoke
npm run test:smoke:headed
```

覆盖页面：
- 豆瓣探索首页
- 更多榜单页
- 电影详情页
- 剧集详情页
- 豆瓣详情页

如果首次运行缺浏览器依赖，可执行：

```bash
cd frontend
npx playwright install chromium
npx playwright install-deps chromium
```

### 后端测试

```bash
cd backend
pytest tests
```

当前测试目录：
- [backend/tests](/mnt/d/code/MediaSync115/backend/tests)

另外包含一个真实联调烟雾脚本：

```bash
python3 backend/tests/run_live_subscription_transfer_smoke.py
```

该脚本会调用正在运行的本地服务，覆盖：
- 订阅队列
- 探索页转存队列
- 剧集转存串行执行

## 主要页面

- `/explore/douban`：豆瓣探索首页
- `/explore/tmdb`：TMDB 探索首页
- `/explore/:source/section/:key`：更多榜单页
- `/movie/:id`：电影详情页
- `/tv/:id`：剧集详情页
- `/douban/:mediaType/:id`：豆瓣详情页
- `/subscriptions`：订阅列表
- `/downloads`：下载列表
- `/logs`：日志页
- `/settings`：设置页
- `/scheduler`：调度页

## 当前实现说明

### 首页探索

- 首页采用分区懒加载
- 后端支持首页预热缓存
- 首页探索和更多榜单都带 Emby 对号状态

### Emby

- Emby 已入库状态已接入卡片和详情页
- Emby 支持全量同步索引
- 剧集完整性可用于缺集判断和对号展示

### 115 转存

- 转存默认直存到 115 默认目录
- 剧集详情页支持选集转存
- HDHive 一键转存和选集转存支持积分解锁提示

## 常见问题

### 1. 为什么后端启动很慢？

当前启动阶段会执行一部分阻塞初始化，例如：
- 数据库初始化
- 调度器初始化
- 首页探索预热

代码位置：
- [backend/main.py](/mnt/d/code/MediaSync115/backend/main.py)

如果你在测试环境里不需要这些启动副作用，建议后续补一个 `TESTING` 开关跳过预热。

### 2. 为什么某些搜索或榜单会受外部服务影响？

因为部分能力依赖外部数据源：
- TMDB
- Nullbr
- Pansou
- HDHive
- Telegram
- Emby
- 115

这些服务波动会直接影响接口耗时和可用性。

### 3. 为什么 Playwright 第一次跑不起来？

通常是两类原因：
- 没装浏览器：执行 `npx playwright install chromium`
- 缺 Linux 运行库：执行 `npx playwright install-deps chromium`

## 开发建议

- 先跑前端构建和 Playwright smoke，再改业务逻辑
- 后端联调前先确认：
  - 115 Cookie 有效
  - TMDB API Key 有效
  - Emby 配置可用
- 对会改真实数据的脚本保持谨慎，尤其是：
  - 订阅扫描
  - 115 删除
  - 实时转存

## License

仓库当前未声明独立 License 文件。如需开源发布，建议补充 `LICENSE`。
