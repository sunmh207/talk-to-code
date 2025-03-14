import json
import os

from biz.chunker import UniversalFileChunker
from biz.repo_manager import RepositoryManager
from dotenv import load_dotenv

from biz.embedder import Embedder
from biz.util.log import logger
from biz.vector_store import VectorStore

load_dotenv()


def confirm_and_execute(config):
    print("\n当前配置如下：")
    for key, value in config.items():
        print(f"{key}: {value}")

    user_input = input("\n请确认以上配置。输入 'y' 继续，或 'n' 退出: ").strip().lower()
    if user_input != 'y':
        print("操作已取消。")
        return False
    return True


def handle_existing_index(url, index_name):
    vector_store = VectorStore(url=url, index_name=index_name)
    if vector_store.index_exists(index_name):
        logger.warning(f"警告：索引 '{index_name}' 已存在！")
        choice = input(
            "请选择操作：\n"
            "o. 覆盖索引\n"
            "i. 增量索引\n"
            "e. 退出\n"
            "请输入选择 (o/i/e): ").strip().lower()

        if choice == 'o':
            logger.info(f"选择覆盖索引 '{index_name}'。")
            return 'overwrite'
        elif choice == 'i':
            logger.info(f"选择增量索引 '{index_name}'。")
            return 'increment'
        elif choice == 'e':
            logger.info("退出程序。")
            return 'exit'
        else:
            logger.info("无效选择，退出程序。")
            return 'exit'
    return None


def add_repo_to_file(data_file_path, config):
    """将新的仓库信息添加到指定的 JSON 文件中，处理文件不存在或为空的情况。"""
    # 检查文件是否存在或为空
    if not os.path.exists(data_file_path) or os.path.getsize(data_file_path) == 0:
        repos = []
    else:
        with open(data_file_path, "r", encoding="utf-8") as f:
            repos = json.load(f)

    # 添加新元素
    repos.append({
        "repo_id": config["repo_id"],
        "index_name": config["index_name"],
        "index_status": "done"
    })

    # 写入文件
    with open(data_file_path, "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=4, ensure_ascii=False)

    logger.info("新仓库信息已成功添加到文件！")


# 交互式获取 repo_id
repo_id = input("请输入 repo_id (格式：group/repo): ")

# 配置字典
config = {
    "repo_id": repo_id,
    "index_name": repo_id.replace("/", "-"),
    "gitlab_access_token": os.getenv("GITLAB_ACCESS_TOKEN"),
    "local_repos_dir": os.getenv('LOCAL_REPOS_DIR', 'data/repos'),
    "gitlab_base_url": os.getenv('GITLAB_BASE_URL'),
    "tokens_per_chunk": int(os.getenv('TOKENS_PER_CHUNK', 800)),
    "MARQO_MAX_CHUNKS_PER_BATCH": 64,
    "marqo_base_url": os.getenv('MARQO_BASE_URL', 'http://localhost:8882')
}

# 执行前确认配置
if not confirm_and_execute(config):
    exit()

# 检查索引是否存在
action = handle_existing_index(config["marqo_base_url"], config["index_name"])
if action == 'exit':
    exit()
elif action == 'increment':
    # 增量索引，暂不支持
    logger.info("增量索引暂不支持。")
    exit()
elif action == 'overwrite':
    # 覆盖索引，删除原有索引
    logger.info(f"正在删除原有索引 '{config['index_name']}'...")
    vector_store = VectorStore(url=config["marqo_base_url"], index_name=config["index_name"])
    vector_store.delete_index()
    logger.info(f"原有索引 '{config['index_name']}' 删除成功。")

# 下载代码仓库
repo_manager = RepositoryManager(
    repo_id=config["repo_id"],
    access_token=config["gitlab_access_token"],
    local_dir=config["local_repos_dir"],
    gitlab_base_url=config["gitlab_base_url"]
)

logger.info(f"正在下载代码仓库 '{config['repo_id']}'...")
repo_manager.download()
logger.info(f"代码仓库 '{config['repo_id']}' 下载成功。")

chunker = UniversalFileChunker(max_tokens=config["tokens_per_chunk"])

# 初始化 embedder，确保使用配置中的参数
embedder = Embedder(
    repo_manager=repo_manager,
    chunker=chunker,
    index_name=config["index_name"],
    url=config["marqo_base_url"]
)

# 执行嵌入数据集操作，确保 chunks_per_batch 从 config 中传递
embedder.embed_dataset(chunks_per_batch=config["MARQO_MAX_CHUNKS_PER_BATCH"])

add_repo_to_file(data_file_path="data/repos.json", config=config)
