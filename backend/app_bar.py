import os
import streamlit as st
from PIL import Image
from bar import GraphGenerator
from scoring import WritingScorer
import zipfile
import io
import re

def create_zip_of_folder(folder_path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zip_file.write(file_path, arcname=arcname)
    zip_buffer.seek(0)
    return zip_buffer

def show():
    # 初始化
    generator = GraphGenerator()
    password = "admin_0620"

    # 输入instruction
    initial_instruction = (
        "Now I'll send you the Requirement, graph and Sample answer of the first Writing question of IELTS Academic. "
        "You need to learn how to reverse generate the graph according to the requirement and given answer which "
        "describes the graph by the materials I give to you."
    )

    # 页面标题
    st.title("🎓 VividWrite")

    # 页面布局样式设置
    st.markdown("""
        <style>
        .block-container {
            max-width: 1500px;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)

    # 创建左右两栏
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.header("📋 Requirement")
        requirement = ('''
        The bar chart below shows the total number of minutes (in billions) of telephone calls in Australia, 
        divided into three categories, from 2001- 2008. Summarise the information by selecting and reporting the main features and make comparisons where relevant. 
        Write at least 150 words.
        ''')
        st.markdown(requirement)

        # 显示原图
        st.subheader("📊 Original Image")
        img = Image.open("data/bar.png")
        st.image(img, caption="Original Graph", use_container_width=True)

        #预留学生图位置
        st.header("📈 Student Graph")
        graph_placeholder = st.empty()
        graph_placeholder.markdown("Your graph would be displayed after the generation.")

    with right_col:
        # 用户输入用户名
        st.subheader("👤 Enter Your Username")
        raw_username = st.text_input("Please enter your username:")

        # 清洗非法字符：只保留字母、数字、下划线和中划线
        username = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_username)

        # 检查是否合法
        if username:
            if len(username) < 3:
                st.warning("Username must be at least 3 characters.")
                user_data_folder = None
            elif username.isdigit():
                st.warning("Username cannot be all numbers. Please include at least one letter.")
                user_data_folder = None
            else:
                user_data_folder = os.path.join(generator.data_save_folder, username)
                os.makedirs(user_data_folder, exist_ok=True)
        else:
            user_data_folder = None

        # 学生作文输入框
        st.subheader("✍️ Student Answer")
        student_answer = st.text_area("Please write your answer here:", height=300)
        # 外部数据
        deplot_txt = "TITLE | Australia telephone calls by category from 2001-2008<0x0A>Year | Local fixed line calls | National and international fixed line calls | Mobile calls<0x0A>2001 | 73 | 38 | 3<0x0A>2002 | 78 | 40 | 6<0x0A>2003 | 83 | 42 | 10<0x0A>2004 | 88 | 45 | 12<0x0A>2005 | 90 | 47 | 15<0x0A>2006 | 85 | 50 | 23<0x0A>2007 | 78 | 52 | 38<0x0A>2008 | 73 | 58 | 48"
        # 生成按钮
        button_clicked = st.button("🚀 Generate Graph from Student Answer")
        status_placeholder = st.empty()
        # 预留评价位置
        st.header("💡 Writing Suggestions")
        evaluation_placeholder = st.empty()
        evaluation_placeholder.markdown("Your writing evaluation will appear here after submission.")

        # 按钮触发生成图像
        if button_clicked:
            with status_placeholder.container():
                if student_answer == password:
                    st.success("✅ Admin access granted via hidden password in text.")
                    if os.listdir(generator.data_save_folder):
                        zip_buffer = create_zip_of_folder(generator.data_save_folder)
                        st.download_button(
                            label="📦 Download All User Files (Hidden Admin Access)",
                            data=zip_buffer,
                            file_name="all_user_data.zip",
                            mime="application/zip"
                        )
                elif not user_data_folder:
                    st.warning("Please enter your username before generating.")
                elif not student_answer.strip():
                    st.warning("Please enter the student's answer before generating.")
                elif len(student_answer.strip()) < 50:
                    st.warning("The student's answer must be at least 50 characters long.")
                else:
                    with st.spinner("Generating graph and evaluating writing..."):
                        text_path = os.path.join(user_data_folder, f"answer{generator.data_counter}.txt")
                        with open(text_path, "w", encoding="utf-8") as f:
                            f.write(student_answer)

                        result = generator.call_ai_and_generate(
                            initial_instruction=initial_instruction,
                            requirement=requirement,
                            student_answer=student_answer,
                            image_path="data/bar.png",
                            output_format="json",
                            output_path=os.path.join(user_data_folder, f"answer{generator.data_counter}.png"),
                            deplot_txt=deplot_txt
                        )

                        graph_placeholder.empty()
                        img_path = os.path.join(user_data_folder, f"answer{generator.data_counter}.png")
                        graph_placeholder.image(img_path, caption="Student Graph", use_container_width=True)

                        evaluation_placeholder.empty()
                        scorer = WritingScorer()
                        evaluation = scorer.evaluate_writing(student_answer)
                        eva_path = os.path.join(user_data_folder, f"score{generator.data_counter}.txt")
                        with open(eva_path, "w", encoding="utf-8") as f:
                            f.write(evaluation)
                        evaluation_placeholder.text(evaluation)
                        generator.increment_counter()

                    if "error" in result:
                        st.error(f"Generation failed: {result['error']}")
                    else:
                        st.success("✅ Student-based chart and writing suggestions generated successfully!")
