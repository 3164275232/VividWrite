import colorsys
import os
import random
from io import BytesIO
import streamlit as st
import json
import re
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Optional
from PIL import Image
from dotenv import load_dotenv
import base64
from sklearn.cluster import MiniBatchKMeans
from deepseek_config import get_deepseek_api_key, get_deepseek_client, get_deepseek_extra_body, get_deepseek_model

# API配置
load_dotenv()  # 加载.env文件
api_key = get_deepseek_api_key()

# 调试：检查API密钥是否正确加载
if not api_key:
    print("Warning: DEEPSEEK_API_KEY environment variable was not found.")
    print("Please check that the .env file exists and is formatted correctly.")
else:
    print("DeepSeek API key loaded.")

class GraphGenerator:
    def __init__(self):
        self.safe_modules = {
            "plt": plt,
            "np": np,
            "math": __import__("math")
        }
        self.client = get_deepseek_client(api_key)
        self.data_save_folder = "generated_data_bar"

        if not os.path.exists(self.data_save_folder):
            os.makedirs(self.data_save_folder)

        self.counter_file_path = os.path.join(self.data_save_folder, "counter.txt")
        if os.path.exists(self.counter_file_path):
            with open(self.counter_file_path, encoding='utf-8') as f:
                self.data_counter = int(f.read())
        else:
            self.data_counter = 1
    def extract_color_palette(self, image_path: str, max_colors: int = 5) -> list:
        def rgb_to_hsv(rgb):
            # 将RGB转为HSV色彩空间
            rgb = np.array(rgb) / 255.0
            maxc = np.max(rgb)
            minc = np.min(rgb)
            v = maxc
            if minc == maxc:
                return (0.0, 0.0, v)
            s = (maxc - minc) / maxc
            rc = (maxc - rgb[0]) / (maxc - minc)
            gc = (maxc - rgb[1]) / (maxc - minc)
            bc = (maxc - rgb[2]) / (maxc - minc)
            h = 0.0
            if rgb[0] == maxc:
                h = bc - gc
            elif rgb[1] == maxc:
                h = 2.0 + rc - bc
            else:
                h = 4.0 + gc - rc
            h = (h / 6.0) % 1.0
            return (h, s, v)

        with Image.open(image_path) as img:
            img = img.convert("RGB")
            if img.width * img.height > 300000:
                img = img.resize((300, 300))  # 保持更多细节

            data = np.array(img)
            pixels = data.reshape(-1, 3)

            # 多维度过滤条件
            filtered_pixels = []
            for pixel in pixels:
                r, g, b = [int(x) for x in pixel]
                h, s, v = rgb_to_hsv(pixel)

                cond1 = v < 0.85  # 排除过亮颜色
                cond2 = s > 0.25  # 保证饱和度
                cond3 = not (abs(r - g) < 25 and abs(g - b) < 25 and abs(r - b) < 25)  # 排除近似灰色
                cond4 = (max(r, g, b) - min(r, g, b)) > 40

            if cond1 and cond2 and cond3 and cond4:
                filtered_pixels.append(pixel)

            if not filtered_pixels:
                return ["#1E90FF", "#FFA500"]  # 默认备用颜色

            pixels = np.array(filtered_pixels, dtype=np.float32)

            # 动态调整聚类数量
            actual_colors = min(max_colors, len(np.unique(pixels, axis=0)))
            if actual_colors < 2:
                return ['#%02x%02x%02x' % tuple(pixels[0])]

            # K-means聚类改进版

            kmeans = MiniBatchKMeans(
                n_clusters=actual_colors,
                random_state=42,
                batch_size=1024,
                n_init=3
            )
            kmeans.fit(pixels)

            # 按聚类大小排序，优先选择主要颜色
            unique, counts = np.unique(kmeans.labels_, return_counts=True)
            sorted_colors = kmeans.cluster_centers_[np.argsort(-counts)]

            # 转换为十六进制
            palette = []
            for color in sorted_colors:
                hex_color = '#%02x%02x%02x' % tuple(color.astype(int))

                # 确保颜色差异度 (与已选颜色对比)
                if not palette or all(
                        self._color_distance(hex_color, c) > 30
                        for c in palette
                ):
                    palette.append(hex_color)
                    if len(palette) >= max_colors:
                        break

            return palette    
    @staticmethod
    def _color_distance(c1: str, c2: str) -> float:
        """计算两个颜色之间的欧氏距离"""

        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

        r1, g1, b1 = hex_to_rgb(c1)
        r2, g2, b2 = hex_to_rgb(c2)
        return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5

    def call_ai_and_generate(self, initial_instruction: str, requirement: str, student_answer: str,
                              image_path: Optional[str] = None, output_format: str = "json", output_path=None,
                              deplot_txt: str = None) -> Dict:
        try:
            system_content = """
            You are a data extractor analyzing IELTS Academic Task 1 student-written answers that describe statistical bar charts.
            
            Your job is to extract and structure all numerical data, trend-based estimates, chart axis labels, and the title of the chart from the student answer, and return the result as a standard Python dictionary object.
            
            Follow these strict rules:
            
            ---
            
            1. **Extract `title`**:
               - This is the title of the chart that the student describes or refers to in the answer.
               - It can be inferred from the student’s description or explicit mention of the chart’s title.
               - Preserve the exact wording and order as it appears in the student answer.
            
            2. **Extract `categories`**:
               - These are the x-axis values (e.g., years, employment types, countries).
               - Categories should be generalized groupings shared across all series (e.g., employment types like "Full-time employment", not "Full-time male").
               - Preserve the order implied by the student answer.
            
            3. **Extract `series`**:
               - Each `series` represents a distinct comparison group (e.g., "Men", "Women", "Group A", "Urban", "Rural").
               - Series values must align with the `categories`.
               - For example, if values are given for "Full-time male" and "Full-time female", then:
                 - `category`: "Full-time"
                 - Two series: "Male", "Female"
               - Determine shared base categories and split distinct groups into separate series by label.
               - If some values are missing for certain series in a category, use `null`.
            
            4. **Trend Handling**:
               - If a student describes a trend (e.g., “from 2 to 46 billion”), interpolate intermediate values linearly.
               - All interpolated values must have a `[est]` prefix.
               - Apply logic for comparative phrases such as:
                 - “slightly higher than X” → `[est]X + 2~5 units`
                 - “slightly lower than Y” → `[est]X - 2~5 units`
                 - “almost the same as” → `[est]X ±1~2 units`
                 - “twice as many” → `[est]2 × X`, etc.
               - Trends should apply independently for each series if specified.
            
            5. **Units**:
               - Keep original units exactly as written (e.g., billion, million, tonnes, minutes, dollars).
            
            6. **Extract `x_label`**:
               - This is the general type of category (e.g., “Year”, “Employment type”, “Country”).
               - Infer based on the student’s description of categories.
            
            7. **Extract `y_label`**:
               - This describes what the numbers represent (e.g., “Leisure time (hours per week)”, “Spending (million dollars)”).
               - Infer it from the descriptions and units in the answer.
            
            ---
            
            8. **Output format must be a valid Python dictionary**, like this:
            
            {
              "title": "<chart title>",
              "x_label": "<string>",
              "y_label": "<string>",
              "categories": ["<category1>", "<category2>", ..., "<categoryN>"],
              "series": [
                {
                  "label": "<series name>",
                  "values": ["<value or [est]value with unit>" OR null, ...]  ← Must match category order
                },
                ...
              ]
            }
            
            ---
            
            9. Do not include any explanation, commentary, or formatting outside the dictionary. Just return the dict.
            """

            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Task Context: {initial_instruction}"},
                {"role": "user", "content": f"Official Requirement: {requirement}"},
                {"role": "user", "content": f"""
                    [BEGIN STUDENT ANSWER]
                    {student_answer}
                    [END STUDENT ANSWER]
                    """}
            ]

            # 提取并添加颜色调色板
            # palette = self.extract_color_palette(image_path)
            response = self.client.chat.completions.create(
                model=get_deepseek_model(),
                messages=messages,
                temperature=0.0,
                max_tokens=1500,
                extra_body=get_deepseek_extra_body(),
            )
            print(response.choices[0].message.content)
            student_txt=response.choices[0].message.content
            try:
                student_data = json.loads(student_txt)
            except json.JSONDecodeError:
                print("Error: The content is not a valid JSON string.")
            return self._process_response(student_data, output_format, output_path, image_path, deplot_txt)

        except Exception as e:
            print(f"API Error: {str(e)}")
            return {"error": str(e)}

    def parse_deplot_data(self, deplot_txt):
        # Split the input text by lines
        lines = deplot_txt.strip().split("<0x0A>")

        # Extract the title (optional, if necessary for context)
        title = lines[0].strip()

        # Extract headers from the second line (labels for categories or series)
        headers = lines[1].split(" | ")

        # Create a dictionary to store the data
        data_dict = {}

        # Determine whether we are dealing with year-based or other category-based data
        if "Year" in headers[0]:
            # The first column is "Year" or similar, handle it as year-based data
            categories = sorted(set([line.split(" | ")[0] for line in lines[2:]]))
            for line in lines[2:]:
                parts = line.split(" | ")
                category = parts[0].strip()

                # Prepare to store data for each category
                data_dict[category] = {headers[i].strip(): self.clean_value(parts[i].strip()) for i in
                                       range(1, len(parts))}

        else:
            # Handle other data types where the first column is a category (e.g., Employment Status)
            categories = sorted(set([line.split(" | ")[0] for line in lines[2:]]))
            for line in lines[2:]:
                parts = line.split(" | ")
                category = parts[0].strip()

                # Prepare to store data for each category
                data_dict[category] = {headers[i].strip(): self.clean_value(parts[i].strip()) for i in
                                       range(1, len(parts))}

        return data_dict

    def convert_to_target_format(self, parsed_data):
        categories = list(parsed_data.keys())
        labels = list(parsed_data[next(iter(parsed_data))].keys())
        series = []

        for label in labels:
            values = [parsed_data[category][label] for category in categories]
            series.append({
                "label": label,
                "values": values
            })

        return {
            "categories": categories,
            "series": series
        }


    def extract_bar_chart_color(self, image_path: str) -> list:
        random_chart_color = lambda: '#%02x%02x%02x' % tuple(
            int(c * 255) for c in colorsys.hls_to_rgb(
                random.random(), random.uniform(0.4, 0.7), random.uniform(0.5, 0.8)
            )
        )
        palette = self.extract_color_palette(image_path, max_colors=5)
        return palette or [random_chart_color()]

        # ① 读图并转 base-64
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_data}"
    
        # ② 构造 messages（把图像和文字放在同一 user 消息里）
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert chart analyzer and descriptive academic writing tutor,such as IELTS Task 1 and data commentary. When I give you a bar chart image, "
                    "analyze the chart legend and return **only** the HEX color values corresponding to each series label, "
                    "in the same order as they appear in the legend. If a color cannot be determined, return 'UNKNOWN'. "
                    "The colors should be returned as a comma-separated list of HEX values, without any additional text or explanation."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri}
                    }
                ],
            },
        ]
    
        # 调用 API 获取颜色信息
        rsp = self.client.chat.completions.create(
            model=get_deepseek_model(),
            messages=messages,
            temperature=0,
            max_tokens=50,
            extra_body=get_deepseek_extra_body(),
        )
    
        # 生成随机颜色
        random_chart_color = lambda: '#%02x%02x%02x' % tuple(
            int(c * 255) for c in colorsys.hls_to_rgb(
                random.random(), random.uniform(0.4, 0.7), random.uniform(0.5, 0.8)
            )
        )
    
        # 获取返回的颜色字符串，假设返回值是逗号分隔的颜色列表
        color_list = rsp.choices[0].message.content.strip()
    
        # 处理返回的颜色字符串，拆分成列表
        color_list = color_list.split(", ")
    
        # 处理颜色列表，替换"UNKNOWN"为随机颜色
        processed_colors = [
            color if color != "UNKNOWN" else random_chart_color() for color in color_list
        ]
    
        return processed_colors

    def clean_value(self, val):
        """清理和转换值为浮点数，处理特殊格式"""
        if val is None:
            return None

        # 如果是字符串，尝试提取数值
        if isinstance(val, str):
            val = val.strip()

            # 处理估计值标记
            if val.startswith("[est]"):
                val = val[5:].strip()

            # 处理百分比
            if val.endswith("%"):
                val = val[:-1].strip()

            # 提取第一个数字序列
            match = re.search(r'[-+]?\d*\.?\d+', val)
            if match:
                try:
                    return float(match.group())
                except ValueError:
                    return None
            return None

        # 如果是数值，直接转换
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def find_best_match_batch(self, target: str, candidates: list, cutoff=0.85) -> Optional[str]:
        """
        使用AI模型批量对比目标类别和所有学生类别，返回最接近的匹配项
        """
        target = target.lower()  # 转为小写字母，标准化输入
        candidates = [candidate.lower() for candidate in candidates]  # 确保所有候选项都是小写

        system_content = """
                                You are a semantic comparison model. Your task is to compare a target phrase with a list of candidate phrases and return the most semantically similar phrase.
                                You will provide a score for each phrase in the format: 'phrase_name: score' (e.g., 'single parents: 0.9').
                                Return only the phrase with the highest score without changing the original phrasing of the candidates.
                                Additionally, if the target phrase is a multi-word phrase that includes multiple concepts (e.g., 'housing, transport and industry'), and the candidate phrase is a simpler or more focused phrase (e.g., 'transport'), you must significantly lower the similarity score if there is no direct overlap of concepts, even if some of the words are shared. The more specific or focused the candidate phrase is compared to the multi-concept target phrase, the lower the score should be.
                                On the other hand, if the target phrase and the candidate phrase share a common core concept or subject, even if one contains additional details or modifiers (e.g., 'debt' vs 'debt interest'), the similarity score should be significantly **higher**. In these cases, the shared core concept should take precedence in determining similarity, and the presence of additional information should not drastically reduce the score.
                                """

        # 动态构建候选短语描述
        candidate_description = "\n".join([f"Candidate {i + 1}: {candidate}" for i, candidate in enumerate(candidates)])

        initial_instruction = f"""
                                Compare the following target phrase with a list of candidate phrases. The target phrase is: "{target}"
                                The candidates are:
                                {candidate_description}

                                For each candidate, provide a similarity score between 0 and 1, where 1 means they are very similar and 0 means they are completely different.
                                If the target phrase contains multiple concepts (e.g., 'housing, transport and industry'), and the candidate phrase is a simpler or more specific phrase (e.g., 'transport'), **you must significantly lower the similarity score** if there is no direct overlap of concepts. In such cases, even if some of the words overlap, the overall similarity score must reflect the fact that the concepts are not fully aligned. The more specific the candidate phrase is, the more drastically the score should be reduced.
                                However, if the target phrase and the candidate phrase share a common core subject or concept, even if one is more specific or includes additional information (e.g., 'debt' vs 'debt interest'), the similarity score should be significantly **higher**. The shared core concept should be the main factor in determining the score, and the additional details should not result in a major reduction in similarity.
                                **The output must exactly match the candidate phrase as provided, including case sensitivity, without any modifications to the phrasing or format.**
                                Only provide the phrase with the highest similarity score, in the format 'phrase_name: score'.
                                Do not modify or alter the original phrasing of the candidate phrases in any way.
                                """

        requirement = """
                                Please return only the matching candidate phrase with the highest similarity score, **exactly as it was provided**, including the same case, without any extra information or modifications.
                                """

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Task Context: {initial_instruction}"},
            {"role": "user", "content": f"Official Requirement: {requirement}"},
            {"role": "user", "content": f"""
                    [BEGIN COMPARISON]
                    Target phrase: {target}
                    {candidate_description}
                    [END COMPARISON]
            """}
        ]

        response = self.client.chat.completions.create(
            model=get_deepseek_model(),
            messages=messages,
            max_tokens=100,
            temperature=0,
            extra_body=get_deepseek_extra_body(),
        )
        print(f"\n{response.choices[0].message.content}")  # 打印响应内容，以便查看格式

        # 解析 AI 的响应并找到相似度最高的匹配项
        similarity_scores = response.choices[0].message.content.strip().split('\n')
        best_match = None
        highest_similarity = 0

        # 遍历分数，选择最佳匹配
        for score in similarity_scores:
            if score:
                # 检查返回格式，确保存在 ':' 分隔符
                if ':' in score:
                    phrase, score_value = score.split(':')
                    try:
                        score_value = float(score_value.strip())
                        # 仅保留相似度高于阈值的类别
                        if score_value > highest_similarity and score_value >= cutoff:
                            highest_similarity = score_value
                            best_match = phrase.strip()  # 确保提取的是类别名，而非对比信息
                    except ValueError:
                        continue  # 如果无法转换为浮动数值，跳过此项
                else:
                    print(f"Skipping invalid format: {score}")  # 打印没有符合预期格式的响应

        return best_match

    def compare_and_generate_json(self, x_label, y_label, deplot_data: Dict, student_data: Dict, image_path: str) -> Dict:
        # 提取估计值序列
        index = 0
        estimated_indexes=[]
        for series in student_data["series"]:
            for value in series["values"]:
                if value is not None and "[est]" in str(value):
                    estimated_indexes.append(index)
                index += 1
    
        def clean_series_data(data_dict):
            """对series中的每个值进行清洗，返回结构相同但值为float"""
            cleaned = data_dict.copy()
            for series in cleaned["series"]:
                series["values"] = [self.clean_value(v) for v in series["values"]]
            return cleaned
    
        cleaned_data = clean_series_data(student_data)
    
        palette = self.extract_bar_chart_color(image_path)
        # palette = self.extract_color_palette(image_path)
    
        labels = []
        student_label = []
        values = []
    
        # 获取 clean_label（已清理的标签）
        clean_label = [series["label"] for series in cleaned_data["series"]]
        clean_value = [series["values"] for series in cleaned_data["series"]]
    
        # 遍历 deplot_data 的系列，进行最佳匹配
        for series in deplot_data["series"]:
            deplot_label = series["label"]
            best_match = self.find_best_match_batch(deplot_label, clean_label)
            if best_match:
    
                labels.append(deplot_label)
                student_label.append(best_match)
                found_value = False  # 标记是否找到对应的 values
                for i in range(len(clean_label)):
                    # 修改这里，确保 clean_label[i] 和 best_match 都不是 None
                    if clean_label[i] and best_match and clean_label[i].lower() == best_match.lower():
                        values.append(clean_value[i])
                        found_value = True
                        break
                if not found_value:
                    print(f"Warning: No values found for label '{deplot_label}'.")
    
        # 处理那些在 student_label 中没有的标签
        for label in clean_label:
            if label not in student_label and label not in labels:
                labels.append(label)
                found_value = False  # 标记是否找到对应的 values
                for i in range(len(clean_label)):
                    # 修改这里，确保 clean_label[i] 和 best_match 都不是 None
                    if clean_label[i] and best_match and clean_label[i].lower() == best_match.lower():
                        values.append(clean_value[i])
                        found_value = True
                        break
                if not found_value:
                    print(f"Warning: No values found for label '{label}'.")
    
        # 打印 labels 和 values 的长度
        print(f"Length of labels: {len(labels)}")
        print(f"Length of values: {len(values)}")
    
        # 确保 labels 和 values 的长度与 cleaned_data["series"] 匹配
        if len(labels) == len(values) == len(cleaned_data["series"]):
            # 排序 series 并更新 cleaned_data["series"]
            for i in range(len(labels)):
                cleaned_data["series"][i]["label"] = labels[i]
                cleaned_data["series"][i]["values"] = values[i]
        else:
            print(f"Error: Length mismatch between labels, values, and cleaned_data['series'].")
            print(f"Labels: {labels}")
            print(f"Values: {values}")
            print(f"Cleaned Data Series: {cleaned_data['series']}")
    
        categories = cleaned_data["categories"]
        series = cleaned_data["series"]
        title = cleaned_data["title"]
    
        json_output = {
              "title": title,
              "categories": categories,
              "x_label": x_label,
              "y_label": y_label,
              "series": series,
              "chart_type": "bar",
              "style": {
                "orientation": "vertical",
                "color_palette": palette,
                "estimated_values": estimated_indexes
              }
        }
        print(json_output)
        return json_output

    def _process_response(self, student_data, output_format: str, output_path, image_path, deplot_txt) -> Dict:
        """
        响应处理方法
        """
        try:
            student_data = student_data
            deplot_data = self.convert_to_target_format(self.parse_deplot_data(deplot_txt))
            x_label = student_data["x_label"] if student_data["x_label"] else None
            y_label = student_data["y_label"] if student_data["y_label"] else None
            data = self.compare_and_generate_json(x_label, y_label, deplot_data, student_data, image_path)
            # 调试：将完整返回内容写入 result.json 便于查看
            with open("result_bar.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("=== Raw Response Content 已保存到 result.json ===")

            if output_format == "json":
                self._plot_from_json(data, output_path)
                return data
            return self._safe_execute_code(str(data))
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def increment_counter(self):
        """递增计数器并保存到文件中"""
        self.data_counter += 1
        with open(self.counter_file_path, "w") as f:
            f.write(str(self.data_counter))

    def _plot_from_json(self, data: Dict, output_path):
        """
        从 JSON 生成柱状图，支持：
        - 横向/纵向显示
        - 缺失值高亮显示
        - 估算值特殊标记
        - 自动处理包含字符串的数值数据
        """
        import numpy as np

        # 初始化图表
        plt.figure(figsize=(12, 6))
        categories = data["categories"]
        num_categories = len(categories)
        y_pos = np.arange(num_categories)
        height = 0.35  # 柱状图宽度
        series = data["series"]
        colors = data.get("style", {}).get("color_palette", ["#1f77b4", "#ff7f0e", "#2ca02c"])
        orientation = data["style"].get("orientation", "horizontal")
        estimated_indexes = data.get("style", {}).get("estimated_values", [])

        # 计算每个系列的估算值
        series_starts = np.cumsum([0] + [len(series_item["values"]) for series_item in series])[:-1]  # 每个系列的起始索引
        series_ends = np.cumsum([len(series_item["values"]) for series_item in series])  # 每个系列的结束索引

        # 遍历每个数据系列
        for idx, series_item in enumerate(series):
            values = series_item["values"]
            label = series_item["label"]
            color = colors[idx % len(colors)]
            offset = (idx - (len(series) - 1) / 2) * height  # 多系列偏移量

            # 预处理数据：分离正常值、缺失值和估算值
            clean_values = []
            missing_mask = []
            estimate_mask = []

            # 获取当前系列的估算值索引
            start_idx = series_starts[idx]
            end_idx = series_ends[idx]

            for i, val in enumerate(values):
                global_index = start_idx + i  # 当前系列内的索引转换为全局索引
                if val is None:
                    clean_values.append(0)  # 缺失值设为0以便显示
                    missing_mask.append(True)
                    estimate_mask.append(False)
                else:
                    clean_values.append(val)
                    missing_mask.append(False)
                    estimate_mask.append(global_index in estimated_indexes)  # 判断该值是否是估算值

            # 绘制柱状图
            if orientation == "horizontal":
                bars = plt.barh(y_pos + offset, clean_values, height,
                                color=color, label=label, alpha=0.7)

                # 标记估算柱
                for i, is_estimate in enumerate(estimate_mask):
                    if is_estimate:
                        bars[i].set_hatch('xx')  # 给柱子加上特殊的填充样式
                        bars[i].set_edgecolor(color)  # 设置柱子的边缘颜色
                        bars[i].set_alpha(0.5)  # 设置透明度

            else:
                bars = plt.bar(y_pos + offset, clean_values, height,
                               color=color, label=label, alpha=0.7)

                # 标记估算柱
                for i, is_estimate in enumerate(estimate_mask):
                    if is_estimate:
                        bars[i].set_hatch('xx')  # 给柱子加上特殊的填充样式
                        bars[i].set_edgecolor(color)  # 设置柱子的边缘颜色
                        bars[i].set_alpha(0.5)  # 设置透明度

            # 高亮缺失值（红色半透明条）
            for i, is_missing in enumerate(missing_mask):
                if is_missing:
                    if orientation == "horizontal":
                        plt.barh(y_pos[i] + offset, 2, height,
                                 color='red', alpha=0.5, hatch='//')
                    else:
                        plt.bar(y_pos[i] + offset, 2, height,
                                color='red', alpha=0.5, hatch='//')

        # 添加图表装饰
        if orientation == "horizontal":
            plt.xlabel(data.get("y_label", "Value"))
            plt.ylabel(data.get("x_label", "Category"))
            plt.yticks(y_pos, categories)
        else:
            plt.ylabel(data.get("y_label", "Value"))
            plt.xlabel(data.get("x_label", "Category"))
            # 根据标签长度自动调整旋转角度
            rotation = 45 if any(len(cat) > 5 for cat in categories) else 0
            plt.xticks(y_pos, categories, rotation=rotation, ha='right' if rotation else 'center')

        # 添加标题和图例
        plt.title(data.get("title", "Student Answer Visualization"))
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        # 自动调整布局
        plt.tight_layout()
        # 保存和显示图像
        data_path = output_path
        plt.savefig(data_path, dpi=300, bbox_inches='tight')
        # self._increment_counter()

        # Streamlit 显示
        # buf = BytesIO()
        # plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        # buf.seek(0)
        # st.image(buf, caption=data.get("title", "Student Graph"), use_container_width=True)
        print(f"Data saved to: {os.path.abspath(data_path)}")

    def _safe_execute_code(self, content: str) -> Dict:
        """
        安全执行代码方法
        """
        code_block = self._extract_code(content)
        if not code_block:
            return {"error": "No valid code block"}
        try:
            restricted_globals = self.safe_modules.copy()
            local_env = {}
            exec(code_block, restricted_globals, local_env)
            # plt.show()
            return {"status": "success", "output": local_env.get("figure")}
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}

    @staticmethod
    def _extract_code(content: str) -> Optional[str]:
        """
        提取代码块方法
        """
        match = re.search(r"```python\s*(.*?)```", content, re.DOTALL)
        return match.group(1).strip() if match else None


# ------------------ 使用示例 ------------------
if __name__ == "__main__":
    # 输入参数配置
    initial_instruction = (
        "Now I'll send you the Requirement, graph and Sample answer of the first Writing question of IELTS Academic. "
        "You need to learn how to reverse generate the graph according to the requirement and given answer which "
        "describes the graph by the materials I give to you."
    )

    # requirement = (
    #     """The pie chart below shows the proportion of different categories of families living in poverty in UK in 2002.
    #     Summarise the information by selecting and reporting the main features, and make comparisons where relevant.
    #     Write at least 150 words."""
    # )
    requirement = (
        """The bar chart below shows the total number of minutes (in billions) of telephone calls in Australia, divided into three categories, from 2001- 2008.

Summarise the information by selecting and reporting the main features and make comparisons where relevant.
Write at least 150 words."""
    )

    # sample_answer = (
    #     "The provided bar chart shows the comparison between the numbers of male and female students enrolling in the "
    #     "research study in six different subjects, like linguistic, psychology, natural science, engineering programming "
    #     "and mathematics at an American University. Overall, the graph shows that there are more male students enrolled in "
    #     "the research field in comparison to female students. As per the provided illustration, both female and male students got "
    #     "an equal number of entries in natural science. As far as mathematics is concerned, male students had greater interest than "
    #     "females. Moreover, male entrants can be seen in all of the subjects except for linguistics. It is clear from the provided data "
    #     "that natural science turned to be the most sought subject for both genders as it recorded 400 entrants altogether (200 on each). "
    #     "In mathematics, men recorded another 200 entries as opposed to merely 50 female students. Additionally, in the psychology subject, "
    #     "there were almost 375 entrants. Even here, male students dominated at 200 and females were at 175. On the other hand, linguistic "
    #     "defined a completely different story as female enrollers toppled the number of male entrants at approximately 120 to 80, respectively."
    # )

    #     student_answer = (
    #         """
    #         The pie chart inspects the different family types living in poor conditions in the UK in 2002.
    # At a glance, in the given year, 14% of the entire households in the country were in circumstances of poverty. In comparison to the couples, singles struggled more. Talking about people with children, single parents presented the maximum percentage of 26% amongst all the specified categories, whereas couples with children reported a comparatively lesser percentage of 15%.
    # As far as the people with no children are concerned, single people were of the hefty percentage, 24%, almost the same number for single people with children. On the contrary, merely 9% of the couples without any children agonized from poverty in 2002. Coming to aged people, singles had a somewhat higher percentage in comparison to couples. Only 7% and 5% of the aged population had difficulties in their living conditions.
    #         """
    #     )
    student_answer = (
        """
        The given chart depicts the time Australian residents spent on varying types of telephone calls between 2001 and 2008.

Local fixed line calls were the highest throughout this period, upsurging from 72 billion minutes to under 90 billion in 2003. Following year, this figure peaked at 90 billion. 
Post this, by 2008, it had a downtrend and fell back to the figure of 2001. Both national and international fixed line calls grew gradually from 38 billion to 61 billion toward the end of the period in question. However, the progress decelerated over the last two years.

Also, dramatic growth can be seen in mobile calls from 2 billion to 46 billion minutes. This increase was specifically noticed between 2005 and 2008. During this time, the mobile phone’s use got tripled. In 2008, although local fixed line calls were still popular, the gap between these three categories narrowed significantly over the second half of this period.

        """
    )

    # 初始化生成器
    generator = GraphGenerator()
    # deplot_txt = "TITLE | Proportion of people from each household type living in poverty<0x0A>All households<0x0A>14% | Single aged person<0x0A>7% <0x0A> Aged couple<0x0A>5% | 5% <0x0A> Couple with children<0x0A>15% | 15% <0x0A> Single, no children<0x0A>24% | 24% <0x0A> Sole parent<0x0A>26% | 26% <0x0A> Couple, no children<0x0A>9% | 9%"
    #
    deplot_txt = "TITLE | Australia telephone calls by category from 2001-2008<0x0A>Year | Local fixed line calls | National and international fixed line calls | Mobile calls<0x0A>2001 | 73 | 38 | 3<0x0A>2002 | 78 | 40 | 6<0x0A>2003 | 83 | 42 | 10<0x0A>2004 | 88 | 45 | 12<0x0A>2005 | 90 | 47 | 15<0x0A>2006 | 85 | 50 | 23<0x0A>2007 | 78 | 52 | 38<0x0A>2008 | 73 | 58 | 48"

    # 执行API调用
    result = generator.call_ai_and_generate(
        initial_instruction=initial_instruction,
        requirement=requirement,
        # sample_answer=sample_answer,
        student_answer=student_answer,
        image_path="data/bar.png",  # 或指定图片路径
        output_format="json",
        output_path="generated_data_bar",
        deplot_txt=deplot_txt
    )

    # 处理结果
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print("Generated Data:")
        print(json.dumps(result, indent=2))
