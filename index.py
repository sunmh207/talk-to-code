import json
import os

from biz.chunker import UniversalFileChunker
from biz.repo_manager import RepositoryManager
from dotenv import load_dotenv

from biz.embedder import Embedder
from biz.util.log import logger
from biz.vector_store import VectorStore

load_dotenv("config/.env")


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
    """将新的仓库信息添加到指定的 JSON 文件中。如果 repo_id 已存在，则更新，否则添加。最终按照 index_name 排序。"""

    # 检查文件是否存在或为空
    if not os.path.exists(data_file_path) or os.path.getsize(data_file_path) == 0:
        repos = []
    else:
        with open(data_file_path, "r", encoding="utf-8") as f:
            try:
                repos = json.load(f)
                if not isinstance(repos, list):  # 兼容性检查，确保数据是列表
                    raise ValueError("JSON 文件格式错误，必须为列表。")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"读取 JSON 文件失败: {e}")
                repos = []

    # 查找是否已有 repo_id
    repo_id = config["repo_id"]
    for repo in repos:
        if repo.get("repo_id") == repo_id:
            # 更新已存在的 repo 信息
            repo["index_name"] = config["index_name"]
            repo["index_status"] = "done"
            break
    else:
        # 如果 for 循环 未执行 break，说明 repo_id 不存在，添加新记录
        repos.append({
            "repo_id": repo_id,
            "index_name": config["index_name"],
            "index_status": "done"
        })
    # 按照 index_name 进行排序（升序）
    repos.sort(key=lambda x: x["index_name"])

    # 写入文件
    with open(data_file_path, "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=4, ensure_ascii=False)

    logger.info(f"仓库信息 {'更新' if any(r['repo_id'] == repo_id for r in repos) else '添加'} 成功！")


# 交互式获取 repo_id
repo_id = input("请输入 repo_id (格式：group/repo): ").strip()
# 确保 repo_id 非空
if not repo_id:
    print("repo_id 不能为空，请重新输入。")
    repo_id = input("请输入 repo_id (格式：group/repo): ").strip()

# 获取分支名输入，并去除前后空格
branch = input("请输入分支名 (不输入则使用默认分支): ").strip()

# 如果用户未输入分支名，返回 None
if not branch:
    branch = None

# 配置字典
config = {
    "repo_id": repo_id,
    "commit_hash": branch,
    "index_name": repo_id.replace("/", "-"),
    "gitlab_access_token": os.getenv("GITLAB_ACCESS_TOKEN"),
    "local_repos_dir": os.getenv('LOCAL_REPOS_DIR', 'data/repos'),
    "gitlab_base_url": os.getenv('GITLAB_BASE_URL'),
    "tokens_per_chunk": int(os.getenv('TOKENS_PER_CHUNK', 800)),
    "marqo_base_url": os.getenv('MARQO_BASE_URL', 'http://localhost:8882'),
    "ignore_file": os.getenv('IGNORE_FILE', "config/.ignore")
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
    commit_hash=config["commit_hash"],
    access_token=config["gitlab_access_token"],
    local_dir=config["local_repos_dir"],
    gitlab_base_url=config["gitlab_base_url"],
    ignore_file=config.get("ignore_file", None)
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
embedder.embed_dataset()

add_repo_to_file(data_file_path="data/repos.json", config=config)
