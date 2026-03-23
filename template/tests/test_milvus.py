import asyncio

import aiohttp


async def test_stream():
    # 替换成你的接口地址
    url = "http://localhost:8001/ui/retrieve-questions"
    data = {"query": "py解释器是什么"}  # 你的请求参数

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            # 逐行/逐段读取响应（流式核心）
            async for chunk in response.content.iter_any():
                # 实时打印每一段收到的数据
                print( chunk.decode('utf-8'), end="|", flush=True)

# 运行测试
asyncio.run(test_stream())


if __name__ == '__main__':
    asyncio.run(test_stream())
