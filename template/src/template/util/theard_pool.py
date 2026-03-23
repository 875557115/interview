import threading
import queue
import time
from typing import Callable, Any, Optional, List
from template.util.logger import get_logger

logger = get_logger("ProductionThreadPool")


class ProductionThreadPool:
    """
    生产级线程池
    特性：
    1. 最大并发数控制
    2. 任务异常捕获与日志记录
    3. 支持任务结果回调
    4. 优雅关闭（等待所有任务完成/强制关闭）
    5. 任务队列长度监控
    6. 线程复用
    """

    def __init__(self, max_workers: int = 5):
        """
        初始化线程池
        :param max_workers: 最大工作线程数，建议根据CPU核心数/业务场景设置（通常CPU核心数*2 + 1）
        """
        if max_workers <= 0:
            raise ValueError("max_workers必须大于0")

        self.max_workers = max_workers
        self.task_queue = queue.Queue()  # 任务队列（线程安全）
        self.workers: List[threading.Thread] = []  # 工作线程列表
        self.is_running = False  # 线程池运行状态
        self.lock = threading.Lock()  # 线程安全锁

    def _worker(self):
        """工作线程核心逻辑：循环获取并执行任务"""
        while self.is_running:
            try:
                # 非阻塞获取任务（超时1秒，避免线程一直阻塞在get()）
                task: tuple[Callable, tuple, dict, Optional[Callable]] = self.task_queue.get(timeout=1)
                func, args, kwargs, callback = task

                # 执行任务并捕获所有异常
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"任务 {func.__name__} 执行成功")

                    # 执行回调函数（如果有）
                    if callback is not None:
                        try:
                            callback(result)
                        except Exception as e:
                            logger.error(f"任务 {func.__name__} 回调函数执行失败: {str(e)}", exc_info=True)
                except Exception as e:
                    logger.error(f"任务 {func.__name__} 执行失败: {str(e)}", exc_info=True)
                    result = None
                finally:
                    # 标记任务完成（避免队列阻塞）
                    self.task_queue.task_done()
            except queue.Empty:
                # 队列为空时继续循环，等待新任务
                continue
            except Exception as e:
                logger.error(f"工作线程异常: {str(e)}", exc_info=True)

    def submit(self, func: Callable, *args, callback: Optional[Callable] = None, **kwargs) -> None:
        """
        提交任务到线程池
        :param func: 要执行的任务函数
        :param args: 任务函数位置参数
        :param callback: 任务执行成功后的回调函数（入参为任务结果）
        :param kwargs: 任务函数关键字参数
        """
        if not self.is_running:
            raise RuntimeError("线程池未启动，无法提交任务")

        if not callable(func):
            raise TypeError("任务必须是可调用对象")

        # 将任务放入队列（线程安全）
        self.task_queue.put((func, args, kwargs, callback))
        logger.info(f"任务 {func.__name__} 已提交到线程池，当前队列长度: {self.task_queue.qsize()}")

    def start(self) -> None:
        """启动线程池"""
        with self.lock:
            if self.is_running:
                logger.warning("线程池已处于运行状态")
                return

            self.is_running = True
            # 创建并启动工作线程
            for i in range(self.max_workers):
                worker = threading.Thread(target=self._worker, name=f"Worker-{i + 1}")
                worker.daemon = True  # 守护线程（主进程退出时自动销毁）
                worker.start()
                self.workers.append(worker)

            logger.info(f"线程池启动成功，最大并发数: {self.max_workers}，工作线程数: {len(self.workers)}")

    def shutdown(self, wait: bool = True, timeout: Optional[float] = None) -> None:
        """
        关闭线程池
        :param wait: 是否等待所有任务执行完成（True=优雅关闭，False=强制关闭）
        :param timeout: 等待任务完成的超时时间（仅wait=True时有效）
        """
        with self.lock:
            if not self.is_running:
                logger.warning("线程池已处于关闭状态")
                return

            # 标记线程池停止运行
            self.is_running = False
            logger.info("线程池开始关闭...")

            # 等待任务队列处理完成（优雅关闭）
            if wait:
                try:
                    # 等待队列任务完成（timeout=None表示无限等待）
                    self.task_queue.join()
                    logger.info("所有任务已执行完成")
                except Exception as e:
                    logger.error(f"等待任务完成时发生异常: {str(e)}", exc_info=True)

            # 等待工作线程退出
            start_time = time.time()
            for worker in self.workers:
                if worker.is_alive():
                    # 等待线程退出（带超时）
                    worker.join(timeout=timeout if timeout is None else max(0, timeout - (time.time() - start_time)))
                    if worker.is_alive():
                        logger.warning(f"工作线程 {worker.name} 未正常退出（超时）")

            # 清空工作线程列表
            self.workers.clear()
            logger.info("线程池已完全关闭")

    def get_queue_size(self) -> int:
        """获取当前任务队列长度"""
        return self.task_queue.qsize()

    def __del__(self):
        """析构函数：确保线程池关闭"""
        if self.is_running:
            self.shutdown(wait=False)


# ------------------------------ 测试示例 ------------------------------
def test_task(num: int) -> int:
    """测试任务函数：模拟耗时操作"""
    time.sleep(1)
    logger.info(f"测试任务 {num} 执行中...")
    return num * 2


def test_callback(result: int) -> None:
    """测试回调函数"""
    logger.info(f"任务回调：任务执行结果为 {result}")


if __name__ == "__main__":
    # 1. 创建线程池（最大并发3）
    thread_pool = ProductionThreadPool(max_workers=3)

    try:
        # 2. 启动线程池
        thread_pool.start()

        # 3. 提交10个测试任务
        for i in range(10):
            thread_pool.submit(test_task, i, callback=test_callback)

        # 4. 等待所有任务执行（模拟主程序运行）
        time.sleep(12)

    except Exception as e:
        logger.error(f"主线程异常: {str(e)}", exc_info=True)
    finally:
        # 5. 优雅关闭线程池
        thread_pool.shutdown(wait=True, timeout=5)
        logger.info("主线程执行完成")
