import json
import os
from typing import List

import gradio as gr
import pandas as pd
import yaml
from dotenv import load_dotenv

from biz.llm.factory import Factory
from biz.util.log import logger
from biz.vector_store import VectorStore, Document

load_dotenv("config/.env")

client = Factory.getClient()

marqo_base_url = os.getenv('MARQO_BASE_URL', 'http://localhost:8882')
vector_store = VectorStore(url=marqo_base_url)
prompt_templates_file = "prompt_templates.yml"
with open(prompt_templates_file, "r") as file:
    prompt_templates = yaml.safe_load(file)
    system_prompt_template = prompt_templates['system_prompt']


# Function to fetch relevant documents
def get_relevant_documents(messages: list, index_name=None):
    history_user_contents = [message["content"] for message in messages if message["role"] == "user"]
    query = " ".join(history_user_contents[-3:])
    return vector_store.search(query=query, top_k=3, index_name=index_name)


# Function to generate system message with documents
def create_system_message(documents: list):
    ref_contents_str = [doc.page_content for doc in documents]
    return system_prompt_template.format(ref_content=ref_contents_str)


def chat_with_llm(messages: list, index_name: str, documents: List[Document]):
    try:
        # 删除掉role为system的消息
        messages = [message for message in messages if message["role"] != "system"]

        # 把背景知识附加在system prompt里
        system_message = create_system_message(documents)

        # 在最后一个role=user消息后插入一个role=system消息
        last_user_index = None
        for i in range(len(messages) - 1, -1, -1):  # Start from the end
            if messages[i]["role"] == "user":
                last_user_index = i
                break

        if last_user_index is not None:
            messages.insert(last_user_index, {"role": "system", "content": system_message})

        logger.info(f"向模型发送的消息: {messages}")
        completions = client.chat_stream(messages)

        # Stream response and yield chunks
        for chunk in completions:
            chat_chunk = client.convert_to_chunk(chunk)
            if chat_chunk.is_chunk() and chat_chunk.content:
                yield chat_chunk.content

    except Exception as e:
        yield f"Error: {str(e)}"


# User message handler
def user(user_message, history: list):
    return "", history + [{"role": "user", "content": user_message}]


# Bot response handler
def bot(history: list, index_name=None):
    """
    Call OpenAI API and return response.
    :param history: Conversation history
    :return: Streaming response from the model
    """
    bot_message = ""
    history.append({"role": "assistant", "content": ""})
    # 获取用户最后3条消息作为query，从marqo中搜索相关文档
    documents = get_relevant_documents(messages=history, index_name=index_name)
    for chunk in chat_with_llm(history, index_name=index_name, documents=documents):
        bot_message += chunk
        history[-1]['content'] = bot_message
        yield history

    # 机器人回复完成后，添加参考链接
    reference_links = {}

    for doc in documents:
        url = doc.metadata.get("url")  # 提取 URL
        if url:
            filename = url.rstrip("/").split("/")[-1]  # 获取文件名（去掉末尾斜杠，按"/"分割）
            reference_links[url] = filename  # 以 URL 作为 Key，防止重复

    if reference_links:
        reference_text = "\n\n**参考资料:**\n" + "\n".join(
            f"- [{filename}]({url})" for url, filename in reference_links.items()
        )
        history[-1]['content'] += reference_text  # 附加链接

    yield history  # 返回最终的完整回复


# 从 JSON 文件读取数据并转换为 DataFrame
def load_repos_to_df():
    with open("data/repos.json", "r") as f:
        repos = json.load(f)
    df = pd.DataFrame(repos)
    return df, repos


with gr.Blocks() as app:
    df, repos = load_repos_to_df()
    index_names = [repo['index_name'] for repo in repos if repo['index_status'] == 'done']

    with gr.Tab("聊天"):
        chatbot = gr.Chatbot(type="messages")
        with gr.Row():
            with gr.Column(scale=1):
                dropdown_index_name = gr.Dropdown(index_names, interactive=True, label="索引(代码库)")
            with gr.Column(scale=4):
                textbox_query = gr.Textbox(label="输入你的问题", placeholder="请输入...")
        with gr.Row():
            clear = gr.Button("清空对话")

            textbox_query.submit(user, [textbox_query, chatbot], [textbox_query, chatbot],
                                 queue=False).then(bot, [chatbot, dropdown_index_name], chatbot)
            clear.click(lambda: None, None, chatbot, queue=False)
    with gr.Tab("代码库"):
        gr.Markdown("代码库列表")
        gr.DataFrame(value=df)
        gr.Markdown("### 给新代码库建立索引")
        gr.Markdown("执行以下命令，并按照提示输入相关信息")
        gr.Code("python index.py")
    with gr.Tab("调试"):
        gr.Markdown("输入文本搜索向量库")
        json_data = gr.Json(label="返回结果")


        def similarity_search(index_name, top_k, query):
            documents = vector_store.search(query=query, top_k=top_k, index_name=index_name)
            return [{"metadata": doc.metadata, "page_content": doc.page_content} for doc in documents]


        with gr.Row():
            with gr.Column(scale=1):
                debug_index_name = gr.Dropdown(index_names, interactive=True, label="选择索引")
            with gr.Column(scale=1):
                debug_top_k = gr.Dropdown([3, 5, 10, 20], interactive=True, label="返回结果数")
            with gr.Column(scale=4):
                debug_query = gr.Textbox(label="输入文本, 按回车搜索向量库", placeholder="请输入...")
                debug_query.submit(similarity_search, [debug_index_name, debug_top_k, debug_query], [json_data],
                                   queue=False)
app.launch()
