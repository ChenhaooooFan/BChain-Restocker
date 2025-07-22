import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt

st.title("B链补货建议工具")

# 上传文件
consumption_file = st.file_uploader("上传耗材消耗文件", type=["csv"])
inventory_file = st.file_uploader("上传库存文件", type=["csv"])

# 用户输入：计算日均值所用天数、补货覆盖周期参数
daily_avg_days = st.number_input("计算日均消耗的天数（例如14）", min_value=1, max_value=30, value=14)
production_days = st.number_input("生产周期（天）", min_value=0, value=8)
shipping_days = st.number_input("运输周期（天）", min_value=0, value=15)
safety_days = st.number_input("安全库存周期（天）", min_value=0, value=12)
total_days = production_days + shipping_days + safety_days

if consumption_file and inventory_file:
    consumption_df = pd.read_csv(consumption_file)
    inventory_df = pd.read_csv(inventory_file)

    # 检查列名是否标准化
    inventory_df.columns = inventory_df.columns.str.strip()

    # 预处理耗材消耗数据
    consumption_df['日期'] = pd.to_datetime(consumption_df['日期'])
    consumption_df = consumption_df.sort_values('日期')
    recent_28_days = consumption_df.tail(28).copy().reset_index(drop=True)
    week1 = recent_28_days.iloc[:14]
    week2 = recent_28_days.iloc[14:]

    # 合计两个时间段的消耗
    week1_totals = week1[['五件套消耗', '感谢卡消耗', '飞机袋消耗', '达人信消耗']].sum()
    week2_totals = week2[['五件套消耗', '感谢卡消耗', '飞机袋消耗', '达人信消耗']].sum()

    # 计算核心指标
    summary_df = pd.DataFrame({
        'Item': ['五件套', '感谢卡', '飞机袋', '达人信'],
        'Week1 Total': week1_totals.values,
        'Week2 Total': week2_totals.values
    })
    summary_df['Growth Rate'] = (
        (summary_df['Week2 Total'] - summary_df['Week1 Total']) / summary_df['Week1 Total'].replace(0, 1)
    ) * 100
    summary_df['Daily Avg'] = summary_df['Week2 Total'] / daily_avg_days
    summary_df['Growth Multiplier'] = 1 + summary_df['Growth Rate'] / 100

    # 平滑增长倍率
    overall_growth = 1 + summary_df['Growth Rate'].mean() / 100
    summary_df['Use Avg Growth'] = summary_df['Growth Multiplier'] > 1.9
    summary_df.loc[summary_df['Use Avg Growth'], 'Growth Multiplier'] = overall_growth

    # 补货数量计算
    summary_df['Restock Qty'] = (
        summary_df['Daily Avg'] * total_days * summary_df['Growth Multiplier']
    ).round().astype(int)

    # 对应名称映射
    item_map = {
        '五件套': '五件套',
        '感谢卡': '感谢卡',
        '飞机袋': '飞机袋',
        '达人信': '达人信'
    }

    # 添加库存合计
    def get_stock_total(material_name):
        try:
            row = inventory_df.loc[inventory_df['耗材物品'] == material_name]
            if not row.empty:
                return row[['在仓数量', '在途数量']].iloc[0].sum()
            else:
                return 0
        except KeyError:
            return 0

    summary_df['库存合计'] = summary_df['Item'].map(lambda x: get_stock_total(item_map.get(x, x)))

    # 判断是否需要补货
    summary_df['需补货'] = summary_df['Restock Qty'] > summary_df['库存合计']
    summary_df['建议补货量'] = summary_df.apply(
        lambda row: row['Restock Qty'] - row['库存合计'] if row['需补货'] else 0, axis=1
    ).astype(int)

    st.subheader("补货建议表")
    st.dataframe(summary_df[['Item', 'Restock Qty', '库存合计', '需补货', '建议补货量']])

# 用条形图展示这两周 vs 上两周
    st.subheader("耗材使用对比图（两周汇总）")
    for idx, row in summary_df.iterrows():
        item = row['Item']
        week1_value = row['Week1 Total']
        week2_value = row['Week2 Total']
        date_start = recent_28_days.iloc[0]['日期'].strftime("%Y-%m-%d")
        date_split = recent_28_days.iloc[14]['日期'].strftime("%Y-%m-%d")
        date_end = recent_28_days.iloc[-1]['日期'].strftime("%Y-%m-%d")

        fig, ax = plt.subplots()
        ax.bar(['前14天', '最近14天'], [week1_value, week2_value], color=['gray', 'skyblue'])
        ax.set_title(f"{item} - 两周期总消耗对比")
        ax.set_ylabel("数量")
        st.pyplot(fig)

        # 文本总结
        direction = "增长" if week2_value > week1_value else ("下降" if week2_value < week1_value else "持平")
        change_pct = abs((week2_value - week1_value) / week1_value * 100) if week1_value else 0
        st.markdown(f"**{item}：**\n- {date_start} 至 {date_split} 消耗总量为 {week1_value}。\n- {date_split} 至 {date_end} 消耗总量为 {week2_value}。\n- 相比前14天，本期消耗**{direction} {change_pct:.2f}%**。")
