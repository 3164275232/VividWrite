# VividWrite 2.0 使用示例

## 基本使用流程

### 1. 启动系统
```bash
# 方法1: 使用启动脚本（推荐）
python start_system.py

# 方法2: 手动启动
# 终端1: 启动后端
cd backend
uvicorn main:app --reload

# 终端2: 启动前端
cd frontend
npm run dev
```

### 2. 访问应用
打开浏览器访问: http://localhost:5173

### 3. 登录系统
- 点击登录按钮进入主界面

### 4. 使用分析功能

#### 输入学生答案
在左侧的写作区域输入学生的IELTS写作答案，例如：

```
The given chart depicts the time Australian residents spent on varying types of telephone calls between 2001 and 2008.

Local fixed line calls were the highest throughout this period, upsurging from 72 billion minutes to under 90 billion in 2003. Following year, this figure peaked at 90 billion. 
Post this, by 2008, it had a downtrend and fell back to the figure of 2001. Both national and international fixed line calls grew gradually from 38 billion to 61 billion toward the end of the period in question. However, the progress decelerated over the last two years.

Also, dramatic growth can be seen in mobile calls from 2 billion to 46 billion minutes. This increase was specifically noticed between 2005 and 2008. During this time, the mobile phone's use got tripled. In 2008, although local fixed line calls were still popular, the gap between these three categories narrowed significantly over the second half of this period.
```

#### 点击分析按钮
点击写作区域上方的"分析文本"按钮

#### 查看结果

**Flowchart 按钮:**
- 显示IELTS写作Task 1的写作流程图
- 提供写作结构和步骤指导
- 包含引言、概述、详细描述等部分说明

**Feedback 按钮:**
点击后显示两个子选项：

- **Visual Feedback**: 
  - 显示生成的图表数据结构
  - 包含图表类型、标题、轴标签等信息
  - 显示数据系列和类别信息

- **Revision Suggestions**:
  - 数据完整性建议
  - 数据准确性建议  
  - 结构组织建议
  - 长度要求建议

## 示例输出

### Visual Feedback 示例
```json
{
  "title": "Australia telephone calls by category from 2001-2008",
  "chart_type": "bar",
  "x_label": "Year",
  "y_label": "Minutes (billions)",
  "categories": ["2001", "2002", "2003", "2004", "2005", "2006", "2007", "2008"],
  "series": [
    {
      "label": "Local fixed line calls",
      "values": [73, 78, 83, 88, 90, 85, 78, 73]
    },
    {
      "label": "National and international fixed line calls", 
      "values": [38, 40, 42, 45, 47, 50, 52, 58]
    },
    {
      "label": "Mobile calls",
      "values": [3, 6, 10, 12, 15, 23, 38, 48]
    }
  ]
}
```

### Revision Suggestions 示例
```json
[
  {
    "type": "structure",
    "message": "图表包含3个数据系列，建议在描述中更清晰地对比这些系列",
    "severity": "low"
  },
  {
    "type": "length", 
    "message": "答案长度可能不足150词，建议添加更多细节和比较",
    "severity": "medium"
  }
]
```

## 高级功能

### 自定义图表类型
可以通过修改前端代码来支持不同的图表类型：

```javascript
const analysisRequest = {
  chart_type: "pie", // 或 "bar"
  requirement: "你的题目要求",
  student_answer: text,
  deplot_data: "你的图表数据"
};
```

### 添加新的修订建议类型
在后端 `main.py` 的 `generate_revision_suggestions` 函数中添加新的建议逻辑：

```python
def generate_revision_suggestions(chart_data: dict, student_answer: str) -> list:
    suggestions = []
    
    # 添加你的自定义建议逻辑
    if some_condition:
        suggestions.append({
            "type": "custom_type",
            "message": "你的建议内容",
            "severity": "medium"
        })
    
    return suggestions
```

## 故障排除

### 常见问题

1. **后端服务无法启动**
   - 检查是否安装了所有依赖: `pip install -r backend/requirements.txt`
   - 检查端口8000是否被占用

2. **前端服务无法启动**
   - 检查是否安装了Node.js和npm
   - 运行 `npm install` 安装前端依赖

3. **分析功能不工作**
   - 检查OpenAI API密钥是否设置
   - 查看浏览器控制台的错误信息
   - 检查后端日志

4. **图表不显示**
   - 检查 `backend/generated_charts/` 目录是否存在
   - 确认静态文件服务配置正确

### 调试模式
启动后端时添加调试参数：
```bash
uvicorn main:app --reload --log-level debug
```

## 扩展开发

### 添加新的图表类型
1. 在 `backend/` 创建新的图表生成器
2. 在 `main.py` 中添加处理逻辑
3. 更新前端以支持新类型

### 自定义UI组件
在 `frontend/src/` 创建新的React组件来显示特定类型的反馈。

### 集成数据库
可以添加数据库来存储分析历史和用户数据。
