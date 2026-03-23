# 导入包
import daily_stock_analysis as dsa

# 示例：分析单只股票（以茅台 600519 为例，具体函数需看包的文档）
# 注意：不同包的函数名/参数可能不同，以下为通用示例
analysis_result = dsa.analyze_daily_stock(
    stock_code="600519",  # 股票代码
    start_date="2026-03-01",  # 起始日期
    end_date="2026-03-10"  # 结束日期
)

# 打印分析结果
print("每日股票分析结果：")
print(analysis_result)
