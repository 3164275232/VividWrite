import colorsys
import os
import random
from io import BytesIO
import random
import colorsys
import streamlit as st
import json
import re
import matplotlib.pyplot as plt
import base64
import numpy as np
from typing import Dict, Optional
from PIL import Image
from dotenv import load_dotenv
from PIL import Image
import base64
import io
from typing import Tuple, Dict
from deepseek_config import get_deepseek_api_key, get_deepseek_client, get_deepseek_model

# # 鍔犺浇 DePlot 妯″瀷锛堝彧鍔犺浇涓€娆★級
# deplot_processor, deplot_model = load_deplot()

# API閰嶇疆
load_dotenv()  # 鍔犺浇.env鏂囦欢
api_key = get_deepseek_api_key()

# 璋冭瘯锛氭鏌PI瀵嗛挜鏄惁姝ｇ‘鍔犺浇
if not api_key:
    print("Warning: DEEPSEEK_API_KEY environment variable was not found.")
    print("Please check that the .env file exists and is formatted correctly.")
else:
    print("DeepSeek API key loaded.")

def parse_txt_to_dict(txt_content: str) -> Dict[str, Optional[float]]:
    lines = txt_content.strip().splitlines()

    # Extract the title from the first line
    title = lines[0].split("|", 1)[-1].strip()  # Title is after the '|' character

    # Initialize the data dictionary
    data = {
        "title": title  # Include the title as part of the dictionary
    }

    # Process each category and value
    for line in lines[1:]:  # Skip the title line
        if "|" in line:
            category, value = [part.strip() for part in line.split("|", 1)]
            if value.lower() == "null":
                data[category] = None
            else:
                percent_match = re.search(r"([\d.]+)%", value)
                if percent_match:
                    data[category] = float(percent_match.group(1))

    return data

class GraphGenerator:
    def __init__(self):
        self.safe_modules = {
            "plt": plt,
            "np": np,
            "math": __import__("math")
        }
        self.client = get_deepseek_client(api_key)
        self.data_save_folder = "generated_data_pie"

        if not os.path.exists(self.data_save_folder):
            os.makedirs(self.data_save_folder)

        self.counter_file_path = os.path.join(self.data_save_folder, "counter.txt")
        if os.path.exists(self.counter_file_path):
            with open(self.counter_file_path, encoding='utf-8') as f:
                self.data_counter = int(f.read())
        else:
            self.data_counter = 1

    def call_ai_and_generate(self, initial_instruction: str, requirement: str, student_answer: str,
                              image_path: Optional[str] = None, output_format: str = "json", output_path = None,
                              deplot_txt: str = None) -> Dict:
        try:
            system_content = """
            You are a data extractor analyzing student-written descriptive writings that describe statistical charts(such as IELTS, Data commentary).

            1. Identify all explicitly mentioned categories related to data (e.g., government spending, population segments, etc.).

            2. For each category:
               - If a percentage value is mentioned (e.g., "12%"), extract it directly.
               - If only an absolute value is given (e.g., "38 billion"), and the total value is not mentioned, you may estimate the percentage using a logical assumption (e.g., based on 100%), but avoid inventing specific totals. The result must still be expressed as a percentage.
               - If **no numerical value** is mentioned at all, **ignore this category completely**. Do not output it, even as `null`.

            3. If multiple categories are combined into a single line (e.g., "housing, transport and industry"), **keep them as a combined category**:
               - Do not split them into individual categories.
               - Example: If "housing, transport and industry" is mentioned with 37 billion, it should appear as:
                 - housing, transport and industry | estimated %

            4. For ambiguous or generic categories like "other spending", "entire households", or "various", **include them as their own category**:
               - Example: "other spending" should be listed as:
                 - other spending | estimated %

            5. If a category is described **relative to another category** (e.g., "about the same as X", "double of Y", "slightly less than Z"):
               - Estimate the percentage based on the described category.
               - Example:
                 - "about the same as health" 鈫?if health is 15%, estimate it as 15%.
                 - "double of defence" 鈫?if defence is 7%, estimate it as 14%.
                 - "slightly less than education" 鈫?if education is 12%, estimate it as around 10-11%.

            6. Handle **vague or comparative descriptions** smartly:
               - Phrases like "almost the same as", "slightly higher than", "a bit lower than" should be translated to estimated percentages:
                 - "almost the same as" 鈫?卤1~2%
                 - "slightly higher than" 鈫?+2~5%
                 - "slightly lower than" 鈫?-2~5%
               - Example:
                 - "almost the same as single people" 鈫?if single people is 24%, estimate it as 23% or 25%.
                 - "slightly higher than aged couples" 鈫?if aged couples is 9%, estimate it as 11%.

            7. Output all values as **percentages**:
               - Final output must only contain percentages (e.g., `15%`).
               - Do not include raw units like 鈥渂illion鈥?or 鈥淎ED鈥?
               - If the category is mentioned but has no numerical value, **completely remove it from the output**.

            8. Your output must be in plain text, using the following structure:

                TITLE | <concise inferred chart title>

                <Category 1> | <percentage>
                <Category 2> | <percentage>
                ...

                * Do not include categories without values.
                * Do not include commentary, explanation, code, or extra formatting.
                * Do not invent or guess any categories that are not clearly stated in the text.


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

            # 鎻愬彇
            response = self.client.chat.completions.create(
                model=get_deepseek_model(),
                messages=messages,
                temperature=0.0,
                max_tokens=1500,
            )
            print(response.choices[0].message.content)

            return self._process_response(response, output_format, output_path, image_path, deplot_txt)

        except Exception as e:
            print(f"API Error: {str(e)}")
            return {"error": str(e)}

    def extract_table_from_image_deplot(self, image_path: str, deplot_txt) -> str:
        # 鍘熷 DePlot 璋冪敤
        # image = Image.open(image_path).convert("RGB")
        # inputs = deplot_processor(images=image, text="Generate underlying data table of the figure below:",
        #                           return_tensors="pt")
        # predictions = deplot_model.generate(**inputs, max_new_tokens=512)
        # raw_text = deplot_processor.decode(predictions[0], skip_special_tokens=True)
        raw_text = deplot_txt

        system_content = """
            You are a data extractor for chart analysis. Your task is to:

            1. Clean and structure the raw DePlot data to be clear and readable.
            2. The format should be:

                TITLE | <concise inferred chart title>

                <Category 1> | <percentage or null>
                <Category 2> | <percentage or null>
                ...

            3. Ensure:
                - Categories are aligned with the original DePlot order.
                - Percentages are preserved, or marked as `null` if missing.
                - No additional commentary or explanation is included.
                - The final output is in plain text format.
            """

        initial_instruction = "Process the raw DePlot output to match the required format."
        requirement = "Transform the raw data into the specified format, with categories and percentages cleanly aligned."

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Task Context: {initial_instruction}"},
            {"role": "user", "content": f"Official Requirement: {requirement}"},
            {"role": "user", "content": f"""
            [BEGIN DEPLOT DATA]
            {raw_text}
            [END DEPLOT DATA]
            """}
        ]

        response = self.client.chat.completions.create(
            model=get_deepseek_model(),
            messages=messages,
            temperature=0.0,
            max_tokens=1500
        )
        print(f"\n{response.choices[0].message.content}")

        cleaned_text = response.choices[0].message.content.strip()
        return cleaned_text

    def find_best_match_batch(self, target: str, candidates: list, cutoff=0.85) -> Optional[str]:
        """
        浣跨敤AI妯″瀷鎵归噺瀵规瘮鐩爣绫诲埆鍜屾墍鏈夊鐢熺被鍒紝杩斿洖鏈€鎺ヨ繎鐨勫尮閰嶉」
        """
        target = target.lower()  # 杞负灏忓啓瀛楁瘝锛屾爣鍑嗗寲杈撳叆
        candidates = [candidate.lower() for candidate in candidates]  # 纭繚鎵€鏈夊€欓€夐」閮芥槸灏忓啓

        system_content = """
                        You are a semantic comparison model. Your task is to compare a target phrase with a list of candidate phrases and return the most semantically similar phrase.
                        You will provide a score for each phrase in the format: 'phrase_name: score' (e.g., 'single parents: 0.9').
                        Return only the phrase with the highest score without changing the original phrasing of the candidates.
                        Additionally, if the target phrase is a multi-word phrase that includes multiple concepts (e.g., 'housing, transport and industry'), and the candidate phrase is a simpler or more focused phrase (e.g., 'transport'), you must significantly lower the similarity score if there is no direct overlap of concepts, even if some of the words are shared. The more specific or focused the candidate phrase is compared to the multi-concept target phrase, the lower the score should be.
                        On the other hand, if the target phrase and the candidate phrase share a common core concept or subject, even if one contains additional details or modifiers (e.g., 'debt' vs 'debt interest'), the similarity score should be significantly **higher**. In these cases, the shared core concept should take precedence in determining similarity, and the presence of additional information should not drastically reduce the score.
                        """

        # 鍔ㄦ€佹瀯寤哄€欓€夌煭璇弿杩?
        candidate_description = "\n".join([f"Candidate {i + 1}: {candidate}" for i, candidate in enumerate(candidates)])

        initial_instruction = f"""
                        Compare the following target phrase with a list of candidate phrases. The target phrase is: "{target}"
                        The candidates are:
                        {candidate_description}

                        For each candidate, provide a similarity score between 0 and 1, where 1 means they are very similar and 0 means they are completely different.
                        If the target phrase contains multiple concepts (e.g., 'housing, transport and industry'), and the candidate phrase is a simpler or more specific phrase (e.g., 'transport'), **you must significantly lower the similarity score** if there is no direct overlap of concepts. In such cases, even if some of the words overlap, the overall similarity score must reflect the fact that the concepts are not fully aligned. The more specific the candidate phrase is, the more drastically the score should be reduced.
                        However, if the target phrase and the candidate phrase share a common core subject or concept, even if one is more specific or includes additional information (e.g., 'debt' vs 'debt interest'), the similarity score should be significantly **higher**. The shared core concept should be the main factor in determining the score, and the additional details should not result in a major reduction in similarity.
                        Only provide the phrase with the highest similarity score, in the format 'phrase_name: score'.
                        Do not modify or alter the original phrasing of the candidate phrases in any way.
                        """

        requirement = """
                        Please return only the matching phrase with the highest similarity score, without any extra information or modifications.
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
            temperature=0
        )
        print(f"\n{response.choices[0].message.content}")  # 鎵撳嵃鍝嶅簲鍐呭锛屼互渚挎煡鐪嬫牸寮?

        # 瑙ｆ瀽 AI 鐨勫搷搴斿苟鎵惧埌鐩镐技搴︽渶楂樼殑鍖归厤椤?
        similarity_scores = response.choices[0].message.content.strip().split('\n')
        best_match = None
        highest_similarity = 0

        # 閬嶅巻鍒嗘暟锛岄€夋嫨鏈€浣冲尮閰?
        for score in similarity_scores:
            if score:
                # 妫€鏌ヨ繑鍥炴牸寮忥紝纭繚瀛樺湪 ':' 鍒嗛殧绗?
                if ':' in score:
                    phrase, score_value = score.split(':')
                    try:
                        score_value = float(score_value.strip())
                        # 浠呬繚鐣欑浉浼煎害楂樹簬闃堝€肩殑绫诲埆
                        if score_value > highest_similarity and score_value >= cutoff:
                            highest_similarity = score_value
                            best_match = phrase.strip()  # 纭繚鎻愬彇鐨勬槸绫诲埆鍚嶏紝鑰岄潪瀵规瘮淇℃伅
                    except ValueError:
                        continue  # 濡傛灉鏃犳硶杞崲涓烘诞鍔ㄦ暟鍊硷紝璺宠繃姝ら」
                else:
                    print(f"Skipping invalid format: {score}")  # 鎵撳嵃娌℃湁绗﹀悎棰勬湡鏍煎紡鐨勫搷搴?

        return best_match

    # def extract_pie_chart_color(self, image_path: str, label_name: str) -> str:
    #     # 鈶?璇诲浘锛岃浆鎹㈡垚 RGB锛屽苟杞?base64
    #     with Image.open(image_path) as img:
    #         img.thumbnail((1000, 1000))
    #
    #         # 杞负 JPEG 骞跺帇缂╀繚瀛樺埌鍐呭瓨
    #         buffer = BytesIO()
    #         img.convert("RGB").save(buffer, format="JPEG", quality=95, optimize=False)
    #
    #         # 缂栫爜涓?base64 瀛楃涓?
    #         encoded_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    #         data_uri = f"data:image/jpeg;base64,{encoded_data}"
    #
    #     # 鈶?鏋勯€?messages锛堟妸鍥惧儚鍜屾枃瀛楁斁鍦ㄥ悓涓€ user 娑堟伅閲岋級
    #     messages = [
    #         {
    #             "role": "system",
    #             "content": (
    #                 "You are an expert chart analyzer. When I give you a pie-chart image "
    #                 "and a target label, return **only** the HEX color of that label "
    #                 "or the word UNKNOWN."
    #             ),
    #         },
    #         {
    #             "role": "user",
    #             "content": [
    #                 {"type": "text", "text": f"Target label: {label_name}"},
    #                 {"type": "image_url", "image_url": {"url": data_uri}},
    #             ],
    #         },
    #     ]
    #
    #     rsp = self.client.chat.completions.create(
    #         model=get_deepseek_model(),
    #         messages=messages,
    #         temperature=0,
    #         max_tokens=5,
    #     )
    #
    #     color = rsp.choices[0].message.content.strip()
    #     if color.startswith("#") and len(color) == 7:
    #         return color
    #     elif color.upper() == "UNKNOWN":
    #         random_chart_color = lambda: '#%02x%02x%02x' % tuple(
    #             int(c * 255) for c in colorsys.hls_to_rgb(
    #                 random.random(),
    #                 random.uniform(0.4, 0.7),
    #                 random.uniform(0.5, 0.8)
    #             )
    #         )
    #         return random_chart_color()
    #
    # def compare_and_generate_json(self, deplot_txt: str, student_txt: str, image_path: str,
    #                               title="Generated Chart") -> Dict:
    #     deplot_data = parse_txt_to_dict(deplot_txt)
    #     student_data = parse_txt_to_dict(student_txt)
    #
    #     categories = []
    #     values = []
    #     categories_match = []
    #     palette = []
    #
    #     # 閬嶅巻 DePlot 鐨勯『搴?
    #     for cat, deplot_val in deplot_data.items():
    #         best_match = self.find_best_match_batch(cat, list(student_data.keys()))  # 浣跨敤鎵归噺瀵规瘮
    #         if best_match:
    #             categories_match.append(best_match)
    #             categories.append(cat)
    #             values.append(student_data[best_match])
    #             palette.append(self.extract_pie_chart_color(image_path, cat))
    #     for cat in student_data:
    #         if cat not in categories and cat not in categories_match:
    #             categories.append(cat)
    #             values.append(student_data[cat])
    #             random_chart_color = lambda: '#%02x%02x%02x' % tuple(int(c * 255) for c in
    #                                                                  colorsys.hls_to_rgb(random.random(),
    #                                                                                      random.uniform(0.4, 0.7),
    #                                                                                      random.uniform(0.5, 0.8)))
    #             palette.append(random_chart_color())
    #     total = sum(values)
    #     if total < 100:
    #         categories.append("Missing")
    #         values.append(round(100 - total, 1))
    #         missing_index = len(categories) - 1
    #         palette.append("#cccccc")  # 缁?Missing 濉炰竴鍙伆鑹?
    #     else:
    #         missing_index = None
    #
    #     json_output = {
    #         "title": title,
    #         "categories": categories,
    #         "x_label": "",
    #         "y_label": "Percentage",
    #         "series": [{"values": values}],
    #         "chart_type": "pie",
    #         "style": {
    #             "color_palette": palette,
    #         }
    #     }
    #     if missing_index is not None:
    #         json_output["style"]["missing_index"] = missing_index
    #     return json_output
    def extract_pie_chart_color(self, image_path: str, label_name: str) -> tuple:
        return (
            random.random(),
            random.random(),
            random.random()
        )

        """
        璇诲彇楗煎浘骞惰繑鍥炴寚瀹氭爣绛剧殑褰掍竴鍖朢GB棰滆壊鍏冪粍(0-1鑼冨洿)
        """
        # 鎵撳紑骞跺帇缂╁浘鐗?
        with Image.open(image_path) as img:
            img.thumbnail((1000, 1000))
            buffer = BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=90, optimize=False)
            encoded_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            data_uri = f"data:image/jpeg;base64,{encoded_data}"

        # Previous vision-model call is unreachable after the local color fallback above.
        messages = [
            {"role": "system", "content": (
                "You are an expert chart analyzer. When I give you a pie-chart image and a target label, "
                "return **only** the RGB values of that label in the format 'R,G,B' or the word 'UNKNOWN'."
            )},
            {"role": "user", "content": [
                {"type": "text", "text": f"Target label: {label_name}"},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]},
        ]
        rsp = self.client.chat.completions.create(
            model=get_deepseek_model(),
            messages=messages,
            temperature=0,
            max_tokens=10,
        )
        raw = rsp.choices[0].message.content.strip()

        # 瑙ｆ瀽杩斿洖鐨凴GB鎴朥NKNOWN
        if raw.upper() == "UNKNOWN":
            # 鐢熸垚闅忔満棰滆壊骞跺綊涓€鍖栧埌0-1鑼冨洿
            return (
                random.random(),
                random.random(),
                random.random()
            )

        # 灏濊瘯瑙ｆ瀽RGB鏍煎紡
        try:
            # 澶勭悊鍚勭鍙兘鐨勬牸寮? "255,0,0", "[255,0,0]", "(255,0,0)"绛?
            clean_raw = raw.strip("[]()")
            r, g, b = map(lambda x: int(x.strip()), clean_raw.split(','))

            # 灏?-255鑼冨洿杞崲涓?-1鑼冨洿
            return (
                r / 255.0,
                g / 255.0,
                b / 255.0
            )
        except Exception:
            # 瑙ｆ瀽澶辫触鏃惰繑鍥為殢鏈洪鑹?
            return (
                random.random(),
                random.random(),
                random.random()
            )

    def compare_and_generate_json(self, deplot_txt: str, student_txt: str, image_path: str) -> Dict:
        deplot_data = parse_txt_to_dict(deplot_txt)
        student_data = parse_txt_to_dict(student_txt)
        title = deplot_data.get("title", "Generated Graph")
        
        categories, values, palette = [], [], []
        matched = set()

        # 鍖归厤骞惰幏鍙栭鑹?
        for cat, _ in deplot_data.items():
            if cat != "title":  # Skip title field
                best = self.find_best_match_batch(cat, list(student_data.keys()))
                if best:
                    categories.append(cat)
                    values.append(student_data[best])
                    palette.append(self.extract_pie_chart_color(image_path, cat))
                    matched.add(best)

        # 鍓╀綑绫诲埆
        for cat, val in student_data.items():
            if cat not in matched and cat not in categories and cat!="title":
                categories.append(cat)
                values.append(val)
                palette.append(self.extract_pie_chart_color(image_path, cat))

        # Handle missing data, if total percentage is less than 100
        total = sum(values)
        if total < 100:
            categories.append("Missing")
            values.append(round(100 - total, 1))
            missing_index = len(categories) - 1
        else:
            missing_index = None

        # Prepare JSON output
        json_output = {
            "title": title,
            "categories": categories,
            "x_label": "",
            "y_label": "Percentage",
            "series": [{"values": values}],
            "chart_type": "pie",
            "style": {
                "color_palette": palette,
            }
        }

        # If there is missing data, include its index
        if missing_index is not None:
            json_output["style"]["missing_index"] = missing_index

        return json_output

    def _process_response(self, response, output_format: str, output_path, image_path, deplot_txt) -> Dict:
        """
        鍝嶅簲澶勭悊鏂规硶
        """
        try:
            student_txt = response.choices[0].message.content
            deplot_txt = self.extract_table_from_image_deplot(image_path, deplot_txt)
            data = self.compare_and_generate_json(deplot_txt, student_txt, image_path)
            # 璋冭瘯锛氬皢瀹屾暣杩斿洖鍐呭鍐欏叆 result.json 渚夸簬鏌ョ湅
            with open("result.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("=== Raw Response Content 宸蹭繚瀛樺埌 result.json ===")

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
        """閫掑璁℃暟鍣ㄥ苟淇濆瓨鍒版枃浠朵腑"""
        self.data_counter += 1
        with open(self.counter_file_path, "w") as f:
            f.write(str(self.data_counter))

    def _plot_from_json(self, data: Dict, output_path):
        categories = data["categories"]
        values = data["series"][0]["values"]
        colors = data.get("style", {}).get("color_palette", None)
        title = data.get("title", "")

        fig, ax = plt.subplots(figsize=(8, 8))

        # 缁樺埗鎵囧舰
        wedges, _ = ax.pie(
            values,
            colors=colors,
            startangle=90,
            radius=1.0,
            wedgeprops=dict(width=1.0, edgecolor='white')
        )

        # 鑻ュ瓨鍦?Missing 绫伙紝缁樺埗鏂滅嚎
        missing_indices = data.get("style", {}).get("missing_index")

        # 濡傛灉鏄暣鏁帮紝杞垚鍒楄〃锛堝吋瀹规棫浠ｇ爜锛?
        if isinstance(missing_indices, int):
            missing_indices = [missing_indices]
        elif not isinstance(missing_indices, list):
            missing_indices = []

        # 閬嶅巻姣忎釜绱㈠紩锛岃繘琛岄珮浜鐞?
        for idx in missing_indices:
            if 0 <= idx < len(wedges):
                wedges[idx].set_facecolor((1.0, 0.3, 0.3, 0.4))  # 鍗婇€忔槑绾㈣壊
                wedges[idx].set_hatch('//')  # 鏂滅嚎濉厖
                wedges[idx].set_edgecolor('black')

        # 璁＄畻瑙掑害锛屾斁缃?label
        angles = [(wedge.theta2 + wedge.theta1) / 2.0 for wedge in wedges]

        for i, angle in enumerate(angles):
            x = np.cos(np.deg2rad(angle))
            y = np.sin(np.deg2rad(angle))

            x_text = 1.2 * x
            y_text = 1.2 * y

            label = f"{categories[i]}\n{values[i]}%"

            ha = 'left' if x >= 0 else 'right'
            ax.text(x_text, y_text, label, ha=ha, va='center', fontsize=10)

        ax.axis('equal')
        plt.title(title, fontsize=12, loc='center', y=1.08)

        plt.tight_layout()

        # 淇濆瓨鍥惧儚锛屽苟浣跨敤閫掑鍚庣殑璁℃暟鍣ㄤ綔涓烘枃浠跺悕
        data_path = output_path
        plt.savefig(data_path)

        # 鍦ㄥ浘褰㈢粯鍒跺畬鎴愬悗閫掑璁℃暟鍣?
        # self._increment_counter()

        # 鏄剧ず鍥惧儚
        # buf = BytesIO()
        # plt.savefig(buf, format="png")
        # buf.seek(0)
        # st.image(buf, caption="Student Graph", use_container_width=True)

        # 杈撳嚭鍥惧儚鐨勮矾寰?
        print(f"Data saved to: {os.path.abspath(self.data_save_folder)}")

    def _safe_execute_code(self, content: str) -> Dict:
        """
        瀹夊叏鎵ц浠ｇ爜鏂规硶
        """
        code_block = self._extract_code(content)
        if not code_block:
            return {"error": "No valid code block"}
        try:
            restricted_globals = self.safe_modules.copy()
            local_env = {}
            exec(code_block, restricted_globals, local_env)
            plt.show()
            return {"status": "success", "output": local_env.get("figure")}
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}

    @staticmethod
    def _extract_code(content: str) -> Optional[str]:
        """
        鎻愬彇浠ｇ爜鍧楁柟娉?
        """
        match = re.search(r"```python\s*(.*?)```", content, re.DOTALL)
        return match.group(1).strip() if match else None


# ------------------ 浣跨敤绀轰緥 ------------------
if __name__ == "__main__":
    # 杈撳叆鍙傛暟閰嶇疆
    initial_instruction = (
        "Now I'll send you the Requirement, graph and Sample answer of the first Writing question of IELTS Academic. "
        "You need to learn how to reverse generate the graph according to the requirement and given answer which "
        "describes the graph by the materials I give to you."
    )

    requirement = (
        """The pie chart below shows the proportion of different categories of families living in poverty in UK in 2002.
        Summarise the information by selecting and reporting the main features, and make comparisons where relevant.
        Write at least 150 words."""
    )
    # requirement = (
    #     """The pie chart gives information on UAE government spending in 2000. The total budget was AED 315 billion.
    #     Summarize the information by selecting and reporting the main features, and make comparisons where relevant.
    #     Write at least 150 words."""
    # )

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

    student_answer = (
        """
        The pie chart inspects the different family types living in poor conditions in the UK in 2002.
At a glance, in the given year, 14% of the entire households in the country were in circumstances of poverty. In comparison to the couples, singles struggled more. Talking about people with children, single parents presented the maximum percentage of 26% amongst all the specified categories, whereas couples with children reported a comparatively lesser percentage of 15%.
As far as the people with no children are concerned, single people were of the hefty percentage, 24%, almost the same number for single people with children. On the contrary, merely 9% of the couples without any children agonized from poverty in 2002. Coming to aged people, singles had a somewhat higher percentage in comparison to couples. Only 7% and 5% of the aged population had difficulties in their living conditions.
        """
    )
    #     student_answer = (
    #             """
    #             The graph communicates the budget created by the UAE government in the year 2000. All in all, the essential targets that the government had were social security, health and education.
    #
    # The largest space is covered by social security, such as pensions, employment assistance and other benefits, making slightly less than one-third of the entire expense. The second highest expense of the budget were health and personal social services. Hospital and medical services covered AED 53 billion, or about 15% of the budget. On the other hand, education cost UAE AED 38 billion, comprising nearly 12% of the entire budget. The government spent approximately 7% of revenue on debt, and just about similar amounts were spent on defence, which was AED 22 billion, and law and order, which comprised AED 17 billion.
    #
    # Expenditure on housing, transport and industry came to a total of AED 37 billion. Lastly, other spending reported for AED 23 billion.
    #             """
    #         )

    # 鍒濆鍖栫敓鎴愬櫒
    generator = GraphGenerator()
    deplot_txt = "TITLE | Proportion of people from each household type living in poverty<0x0A>All households<0x0A>14% | Single aged person<0x0A>7% <0x0A> Aged couple<0x0A>5% | 5% <0x0A> Couple with children<0x0A>15% | 15% <0x0A> Single, no children<0x0A>24% | 24% <0x0A> Sole parent<0x0A>26% | 26% <0x0A> Couple, no children<0x0A>9% | 9%"
    # 鎵цAPI璋冪敤
    result = generator.call_ai_and_generate(
        initial_instruction=initial_instruction,
        requirement=requirement,
        # sample_answer=sample_answer,
        student_answer=student_answer,
        image_path="data/pie.png",  # 鎴栨寚瀹氬浘鐗囪矾寰?
        output_format="json",
        output_path="generated_data_pie",
        deplot_txt=deplot_txt
    )

    # 澶勭悊缁撴灉
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print("Generated Data:")
        print(json.dumps(result, indent=2))

