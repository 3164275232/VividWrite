# VividWrite 2.0 运行指南

## 📋 前置要求

1. **Python 3.8+**
2. **Node.js 16+** 和 **npm**
3. **OpenAI API Key**（用于图表分析功能）

## 🔧 第一步：环境配置

### 1. 创建环境变量文件

#### 后端环境变量 (backend/.env)
```bash
# 在backend目录下创建.env文件
OPENAI_API_KEY=your_openai_api_key_here
```

#### 前端环境变量 (frontend/.env)
```bash
# 在frontend目录下创建.env文件
VITE_API_BASE=http://localhost:8000
```

### 2. 获取OpenAI API Key
1. 访问 [OpenAI官网](https://platform.openai.com/)
2. 注册/登录账户
3. 在API Keys页面创建新的API密钥
4. 将密钥复制到backend/.env文件中

## 🚀 第二步：安装依赖

### 后端依赖安装
```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 前端依赖安装
```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install
```

## 🎯 第三步：启动服务

### 方法1：手动启动（推荐用于开发）

#### 启动后端服务
```bash
# 在backend目录下
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 启动前端服务
```bash
# 在新终端中，进入frontend目录
cd frontend
npm run dev
```

### 方法2：使用启动脚本
```bash
# 在项目根目录下
python start_system.py
```

## 🌐 第四步：访问应用

1. **前端应用**: http://localhost:5173
2. **后端API**: http://localhost:8000
3. **API文档**: http://localhost:8000/docs

## 🧪 第五步：测试功能

### 1. 基本功能测试
1. 打开浏览器访问 http://localhost:5173
2. 点击登录按钮进入主界面
3. 查看Flowchart标签页的写作指导

### 2. 分析功能测试
1. 在写作区域输入学生答案，例如：
```
The given chart depicts the time Australian residents spent on varying types of telephone calls between 2001 and 2008.

Local fixed line calls were the highest throughout this period, upsurging from 72 billion minutes to under 90 billion in 2003. Following year, this figure peaked at 90 billion. 
Post this, by 2008, it had a downtrend and fell back to the figure of 2001. Both national and international fixed line calls grew gradually from 38 billion to 61 billion toward the end of the period in question. However, the progress decelerated over the last two years.

Also, dramatic growth can be seen in mobile calls from 2 billion to 46 billion minutes. This increase was specifically noticed between 2005 and 2008. During this time, the mobile phone's use got tripled. In 2008, although local fixed line calls were still popular, the gap between these three categories narrowed significantly over the second half of this period.
```

2. 点击"分析文本"按钮
3. 查看Visual Feedback标签页的图表数据
4. 查看Revision Suggestions标签页的改进建议

### 3. API测试
```bash
# 运行测试脚本
python test_integration.py
```

## 🔧 故障排除

### 常见问题

#### 1. 后端启动失败
```bash
# 检查Python版本
python --version

# 检查依赖是否安装完整
pip list

# 检查端口是否被占用
netstat -ano | findstr :8000  # Windows
lsof -i :8000  # macOS/Linux
```

#### 2. 前端启动失败
```bash
# 检查Node.js版本
node --version
npm --version

# 清除缓存重新安装
rm -rf node_modules package-lock.json
npm install
```

#### 3. API调用失败
- 检查OpenAI API Key是否正确设置
- 检查网络连接
- 查看浏览器控制台错误信息
- 查看后端日志

#### 4. 图表生成失败
- 确保OpenAI API Key有效且有足够额度
- 检查输入的学生答案格式
- 查看后端错误日志

### 日志查看

#### 后端日志
```bash
# 启动时查看详细日志
uvicorn main:app --reload --log-level debug
```

#### 前端日志
- 打开浏览器开发者工具 (F12)
- 查看Console标签页的错误信息

## 📊 性能优化

### 开发环境
- 使用虚拟环境隔离依赖
- 启用热重载 (--reload)
- 使用开发模式启动前端

### 生产环境
```bash
# 后端生产部署
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 前端构建
cd frontend
npm run build
```

## 🔄 更新和维护

### 更新依赖
```bash
# 后端
pip install --upgrade -r requirements.txt

# 前端
npm update
```

### 清理缓存
```bash
# 清理Python缓存
find . -type d -name "__pycache__" -delete

# 清理npm缓存
npm cache clean --force
```

## 📞 获取帮助

如果遇到问题，请：
1. 检查本文档的故障排除部分
2. 查看项目README文件
3. 检查GitHub Issues
4. 联系开发团队
