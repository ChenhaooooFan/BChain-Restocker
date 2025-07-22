import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt

st.title("B-chain Restocking Assistant")

# Upload files
consumption_file = st.file_uploader("Upload consumption data", type=["csv"])
inventory_file = st.file_uploader("Upload inventory data", type=["csv"])

# User parameters
daily_avg_days = st.number_input("Days to calculate daily average (e.g. 14)", min_value=1, max_value=30, value=14)
production_days = st.number_input("Production time (days)", min_value=0, value=8)
shipping_days = st.number_input("Shipping time (days)", min_value=0, value=15)
safety_days = st.number_input("Safety stock buffer (days)", min_value=0, value=12)
total_days = production_days + shipping_days + safety_days

if consumption_file and inventory_file:
    consumption_df = pd.read_csv(consumption_file)
    inventory_df = pd.read_csv(inventory_file)
    inventory_df.columns = inventory_df.columns.str.strip()

    consumption_df['日期'] = pd.to_datetime(consumption_df['日期'])
    consumption_df = consumption_df.sort_values('日期')
    recent_28_days = consumption_df.tail(28).copy().reset_index(drop=True)
    week1 = recent_28_days.iloc[:14]
    week2 = recent_28_days.iloc[14:]

    week1_totals = week1[['五件套消耗', '感谢卡消耗', '飞机袋消耗', '达人信消耗', '引流卡消耗']].sum()
    week2_totals = week2[['五件套消耗', '感谢卡消耗', '飞机袋消耗', '达人信消耗', '引流卡消耗']].sum()

    summary_df = pd.DataFrame({
        'Item': ['五件套', '感谢卡', '飞机袋', '达人信', '引流卡'],
        'Week1 Total': week1_totals.values,
        'Week2 Total': week2_totals.values
    })
    summary_df['Growth Rate'] = (
        (summary_df['Week2 Total'] - summary_df['Week1 Total']) / summary_df['Week1 Total'].replace(0, 1)
    ) * 100
    summary_df['Daily Avg'] = summary_df['Week2 Total'] / daily_avg_days
    summary_df['Growth Multiplier'] = 1 + summary_df['Growth Rate'] / 100

    overall_growth = 1 + summary_df['Growth Rate'].mean() / 100
    summary_df['Use Avg Growth'] = summary_df['Growth Multiplier'] > 1.9
    summary_df.loc[summary_df['Use Avg Growth'], 'Growth Multiplier'] = overall_growth

    summary_df['Restock Qty'] = (
        summary_df['Daily Avg'] * total_days * summary_df['Growth Multiplier']
    ).round().astype(int)

    item_map = {
        '五件套': '五件套',
        '感谢卡': '感谢卡',
        '飞机袋': '飞机袋',
        '达人信': '达人信',
        '引流卡': '引流卡'
    }

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
    summary_df['需补货'] = summary_df['Restock Qty'] > summary_df['库存合计']
    summary_df['建议补货量'] = summary_df.apply(
        lambda row: row['Restock Qty'] - row['库存合计'] if row['需补货'] else 0, axis=1
    ).astype(int)

    st.subheader("Restocking Recommendation")
    st.dataframe(summary_df[['Item', 'Restock Qty', '库存合计', '需补货', '建议补货量']])

    # Combined bar chart
    st.subheader("Two-Week Consumption Comparison")
    date_start = recent_28_days.iloc[0]['日期'].strftime("%Y-%m-%d")
    date_split = recent_28_days.iloc[14]['日期'].strftime("%Y-%m-%d")
    date_end = recent_28_days.iloc[-1]['日期'].strftime("%Y-%m-%d")

    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(summary_df))
    ax.bar([i - 0.2 for i in x], summary_df['Week1 Total'], width=0.4, label=f"{date_start} - {date_split}", color='gray')
    ax.bar([i + 0.2 for i in x], summary_df['Week2 Total'], width=0.4, label=f"{date_split} - {date_end}", color='skyblue')
    ax.set_xticks(list(x))
    display_labels = ['Tool Kit', 'Thank You Card', 'Bubble Mailing', 'Influencer Note', 'Promo Card']
    ax.set_xticklabels(display_labels)
    ax.set_ylabel("Quantity")
    ax.set_title(f"Total Usage Comparison: {date_start} - {date_end}")
    ax.legend()
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    st.pyplot(fig)

    # Text summary
    for idx, row in summary_df.iterrows():
        item = row['Item']
        week1_value = row['Week1 Total']
        week2_value = row['Week2 Total']
        direction = "increased" if week2_value > week1_value else ("decreased" if week2_value < week1_value else "remained stable")
        change_pct = abs((week2_value - week1_value) / week1_value * 100) if week1_value else 0
        st.markdown(f"**{item}:**\n- {date_start} to {date_split}: {week1_value} units.\n- {date_split} to {date_end}: {week2_value} units.\n- Compared to the previous 14 days, usage has **{direction} by {change_pct:.2f}%**.")
