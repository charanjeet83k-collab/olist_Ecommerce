"""
OLIST BRAZILIAN E-COMMERCE - STREAMLIT DASHBOARD (one file)
Same five pages as the Power BI report: Executive Overview | Sales & Product | Customers & Reviews | Delivery & Logistics | Payment & Geography,
plus a data-quality page. Filters (slicers) are in the sidebar and apply to all five dashboard pages.
Run:    streamlit run app.py
Login:  APP_USER and APP_PASSWORD (environment variables or .streamlit/secrets.toml). No password is stored in the code.
Needs:  python olist_analysis.py
"""
import hmac, json, os
import numpy as np, pandas as pd, streamlit as st
from olist_analysis import PROCESSED_DIR, REPORTS_DIR

st.set_page_config(page_title="Olist dashboard", page_icon=":bar_chart:", layout="wide")
TEAL, AMBER = "#348E90", "#D98E1F"
st.markdown("""<style>
.block-container{padding-top:1rem;padding-bottom:1rem}
[data-testid=stSidebar]{background:#E3F1F1}
.hdr{background:linear-gradient(90deg,#1F6F72,#348E90);color:#fff;padding:14px 22px;border-radius:12px;border-bottom:4px solid #D98E1F;margin-bottom:12px}
.hdr h2{margin:0;color:#fff;font-size:26px}.hdr p{margin:2px 0 0 0;color:#E3F1F1;font-size:13px}
.kpi{background:#fff;border-radius:10px;padding:10px 14px;border-left:5px solid #348E90;box-shadow:0 1px 5px rgba(0,0,0,.13)}
.kpi .l{font-size:12px;color:#6B6B6B}.kpi .v{font-size:25px;font-weight:700;color:#1F6F72}
.ins{background:#FFF4DC;border-left:5px solid #D98E1F;border-radius:6px;padding:8px 12px;font-size:14px;margin-top:6px}
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------------- login
def credentials():
    try:
        return st.secrets["APP_USER"], st.secrets["APP_PASSWORD"]
    except Exception:
        return os.environ.get("APP_USER"), os.environ.get("APP_PASSWORD")

def require_login():
    user, pwd = credentials()
    if not user or not pwd:
        st.error("Login is not configured. Set APP_USER and APP_PASSWORD (see README)."); st.stop()
    if st.session_state.get("auth_ok"):
        return
    st.markdown('<div class="hdr"><h2>Olist analytics</h2><p>Please sign in</p></div>', unsafe_allow_html=True)
    u = st.text_input("User ID"); p = st.text_input("Password", type="password")
    if st.button("Sign in"):
        if hmac.compare_digest(u, user) and hmac.compare_digest(p, pwd):
            st.session_state["auth_ok"] = True; st.rerun()
        else:
            st.error("Wrong user ID or password.")
    st.stop()

# ---------------------------------------------------------------- data and helpers
@st.cache_data
def load_orders():
    o = pd.read_csv(PROCESSED_DIR / "order_level.csv.gz", parse_dates=["order_purchase_timestamp"]); o["month_no"] = o.order_purchase_timestamp.dt.month; return o

@st.cache_data
def load_items():
    return pd.read_csv(PROCESSED_DIR / "item_level.csv.gz", parse_dates=["order_purchase_timestamp"])

@st.cache_data
def load_payments():
    return pd.read_csv(PROCESSED_DIR / "payment_level.csv.gz")

def header(title, sub):
    st.markdown(f'<div class="hdr"><h2>{title}</h2><p>{sub}</p></div>', unsafe_allow_html=True)

def kpis(items):
    for col, (label, value) in zip(st.columns(len(items)), items):
        col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div></div>', unsafe_allow_html=True)
    st.write("")

def panel(title):
    box = st.container(border=True); box.markdown(f"**{title}**"); return box

def insight(text):
    st.markdown(f'<div class="ins"><b>Insight:</b> {text}</div>', unsafe_allow_html=True)

R = lambda x: f"R$ {x:,.0f}"; P = lambda x: f"{100 * x:.2f}%"; N = lambda x: f"{x:,.0f}"; D = lambda x: f"{x:,.2f}"

# ---------------------------------------------------------------- dashboard pages (filters are applied before these run)
def page_overview(fo, fi, fp):
    header("Executive Overview", "Business health at a glance")
    s = fo[fo.is_sales_order]; si = fi[fi.order_id.isin(s.order_id)]
    kpis([("Orders (valid)", N(len(s))), ("Item sales", R(s.item_sales.sum())), ("Unique customers", N(fo.customer_unique_id.nunique())), ("Active sellers", N(si.seller_id.nunique())), ("Avg review score", D(fo.review_score.mean()) if fo.review_score.notna().any() else "-")])
    m = s.groupby("purchase_month").agg(orders=("order_id", "count"), item_sales=("item_sales", "sum")); a, b = st.columns(2)
    with a.container(border=True): st.markdown("**Item sales per month (R$)**"); st.line_chart(m.item_sales, color=TEAL)
    with b.container(border=True): st.markdown("**Orders per month**"); st.bar_chart(m.orders, color=AMBER)
    a, b, c = st.columns(3); cat = si.groupby("category").price.sum().nlargest(10).sort_values()
    with a.container(border=True): st.markdown("**Top 10 categories by item sales**"); st.bar_chart(cat, horizontal=True, color=TEAL)
    with b.container(border=True): st.markdown("**Valid orders by customer state**"); st.bar_chart(s.groupby("customer_state").size().sort_values(ascending=False), color=TEAL)
    with c.container(border=True): st.markdown("**Orders by status**"); st.bar_chart(fo.order_status.value_counts(), color=AMBER)
    if len(m) and len(cat): insight(f"Item sales peak in {m.item_sales.idxmax()} ({R(m.item_sales.max())}). The top category, {cat.index[-1]}, holds {100 * cat.iloc[-1] / si.price.sum():.1f}% of item sales in this selection.")

def page_sales(fo, fi, fp):
    header("Sales & Product Performance", "Categories, sellers, price and freight (canceled and unavailable orders excluded)")
    si = fi[fi.order_id.isin(fo[fo.is_sales_order].order_id)]
    if si.empty: st.warning("No items in this selection."); return
    kpis([("Item sales", R(si.price.sum())), ("Items sold", N(len(si))), ("Avg item price", D(si.price.mean())), ("Avg freight per item", D(si.freight_value.mean())), ("Freight share of item sales", P(si.freight_value.sum() / si.price.sum()))])
    a, b = st.columns(2); cat = si.groupby("category").price.sum().sort_values(ascending=False)
    with a.container(border=True): st.markdown("**Top 10 categories by item sales (R$)**"); st.bar_chart(cat.head(10).sort_values(), horizontal=True, color=TEAL)
    with b.container(border=True): st.markdown("**Category share of item sales (top 15)**"); st.dataframe((100 * cat / cat.sum()).head(15).round(2).rename("share %"), use_container_width=True)
    a, b = st.columns(2); sel = si.groupby("seller_id").price.sum().sort_values(ascending=False)
    with a.container(border=True): st.markdown("**Top 10 sellers by item sales (R$)**"); st.bar_chart(sel.head(10).sort_values(), horizontal=True, color=AMBER)
    with b.container(border=True):
        st.markdown("**Monthly item sales by year (R$)**"); st.line_chart(si.assign(y=si.order_purchase_timestamp.dt.year, m=si.order_purchase_timestamp.dt.month).groupby(["m", "y"]).price.sum().unstack())
    insight(f"{len(sel):,} sellers sold items; the top 10 hold {100 * sel.head(10).sum() / sel.sum():.1f}% of item sales and {int((100 * sel.cumsum() / sel.sum() < 50).sum() + 1)} sellers generate half of them.")

def page_customers(fo, fi, fp):
    header("Customers & Reviews", "Who the customers are and how satisfied they are")
    per = fo.groupby("customer_unique_id").order_id.nunique(); rv = fo.review_score.dropna()
    kpis([("Unique customers", N(len(per))), ("Repeat customer rate", P((per > 1).mean())), ("Avg review score", D(rv.mean()) if len(rv) else "-"), ("% orders scoring 4-5", P((rv >= 4).mean()) if len(rv) else "-"), ("% orders scoring 1-2", P((rv <= 2).mean()) if len(rv) else "-")])
    a, b = st.columns(2)
    with a.container(border=True): st.markdown("**Order-level review score (rounded)**"); st.bar_chart(rv.round().astype(int).value_counts().sort_index(), color=AMBER)
    with b.container(border=True): st.markdown("**Average review score per month**"); st.line_chart(fo.groupby("purchase_month").review_score.mean(), color=TEAL)
    a, b = st.columns(2)
    with a.container(border=True): st.markdown("**Unique customers by state**"); st.bar_chart(fo.groupby("customer_state").customer_unique_id.nunique().sort_values(ascending=False), color=TEAL)
    with b.container(border=True): st.markdown("**One-time vs repeat customers**"); st.bar_chart(pd.Series({"One-time": int((per == 1).sum()), "Repeat": int((per > 1).sum())}), color=AMBER)
    insight(f"{100 * (per > 1).mean():.2f}% of customers in this selection ordered more than once; {100 * (rv <= 2).mean():.2f}% of reviewed orders scored 1 or 2." if len(rv) else "No reviews in this selection.")

def page_delivery(fo, fi, fp):
    header("Delivery & Logistics", "Delivered orders with a valid date sequence; late = delivered after the estimated date")
    v = fo[fo.valid_delivery]
    if v.empty: st.warning("No delivered orders in this selection."); return
    late = v[v.is_late == 1]
    kpis([("Avg delivery days", D(v.delivery_days.mean())), ("Avg promised days", D(v.estimated_days.mean())), ("On-time delivery", P(1 - v.is_late.mean())), ("Late delivery", P(v.is_late.mean())), ("Avg delay (late orders), days", D(late.delay_days.mean()) if len(late) else "-")])
    a, b = st.columns(2)
    with a.container(border=True): st.markdown("**Average delivery days by customer state**"); st.bar_chart(v.groupby("customer_state").delivery_days.mean().sort_values(), color=TEAL)
    with b.container(border=True): st.markdown("**Late deliveries % per month**"); st.line_chart(100 * v.groupby("purchase_month").is_late.mean(), color=AMBER)
    a, b = st.columns(2)
    with a.container(border=True): st.markdown("**Actual vs promised delivery days per month**"); st.line_chart(v.groupby("purchase_month")[["delivery_days", "estimated_days"]].mean())
    d = v.dropna(subset=["review_score"]).copy(); d["bucket"] = pd.cut(d.delay_days, [-1e9, 0, 3, 7, 1e9], labels=["on time or early", "1-3 days late", "4-7 days late", "over 7 days late"])
    sc = d.groupby("bucket", observed=True).review_score.mean()
    with b.container(border=True): st.markdown("**Average review score by delay**"); st.bar_chart(sc, color="#4A6F8A")
    if len(sc) == 4: insight(f"Orders delivered on time score {sc.iloc[0]:.2f} on average and orders more than 7 days late score {sc.iloc[3]:.2f}. This is an observed association; the data cannot show why.")

def page_payment(fo, fi, fp):
    header("Payment & Geographic Insights", "How customers pay and where they are (payment total includes freight and covers all orders with payments)")
    if fp.empty: st.warning("No payments in this selection."); return
    val = fp.groupby("payment_type").payment_value.sum().sort_values(ascending=False); s = fo[fo.is_sales_order]
    kpis([("Payment total", R(fp.payment_value.sum())), ("Avg payment per order", D(fp.payment_value.sum() / fp.order_id.nunique())), ("Credit-card share of value", P(val.get("credit_card", 0) / val.sum())), ("Avg instalments", D(fp.payment_installments.mean())), ("Cities served", N(fo.customer_city.nunique()))])
    a, b = st.columns(2)
    with a.container(border=True): st.markdown("**Payment value by payment type (R$)**"); st.bar_chart(val, color=TEAL)
    with b.container(border=True): st.markdown("**Credit-card payments by number of instalments**"); st.bar_chart(fp[fp.payment_type == "credit_card"].payment_installments.value_counts().sort_index(), color=AMBER)
    a, b = st.columns(2); bystate = fp.merge(fo[["order_id", "customer_state"]], on="order_id").groupby("customer_state").payment_value.sum().sort_values(ascending=False)
    with a.container(border=True): st.markdown("**Payment total by customer state (R$)**"); st.bar_chart(bystate, color=TEAL)
    with b.container(border=True): st.markdown("**Top 10 cities by valid orders**"); st.bar_chart(s.groupby("customer_city").size().nlargest(10).sort_values(), horizontal=True, color=AMBER)
    insight(f"Credit card carries {100 * val.get('credit_card', 0) / val.sum():.1f}% of payment value in this selection; {bystate.index[0]} has the largest payment total.")

def page_quality():
    st.title("Data quality audit")
    df = pd.read_csv(REPORTS_DIR / "data_quality_report.csv")
    status = st.multiselect("Status", ["Issue", "Info", "No issue"], default=["Issue"])
    st.dataframe(df[df.status.isin(status)], use_container_width=True)
    st.caption("Counts come from the Python audit of the original CSV files. Issues are flagged in the cleaned views, not deleted.")

# ---------------------------------------------------------------- navigation and filters
require_login()
DASH = {"Executive Overview": page_overview, "Sales & Product": page_sales, "Customers & Reviews": page_customers, "Delivery & Logistics": page_delivery, "Payment & Geography": page_payment}
st.sidebar.markdown("### Olist dashboard")
PAGE = st.sidebar.radio("Page", list(DASH) + ["Data quality"])
if PAGE in DASH:
    o, items, pays = load_orders(), load_items(), load_payments()
    st.sidebar.markdown("---"); st.sidebar.markdown("**Filters (slicers)**")
    years = sorted(o.purchase_year.dropna().unique().astype(int)); months = list(range(1, 13)); states = sorted(o.customer_state.dropna().unique())
    cats = sorted(o.category.dropna().unique()); statuses = sorted(o.order_status.dropna().unique())
    sy = st.sidebar.multiselect("Year", years, default=years); sm = st.sidebar.multiselect("Month (1-12)", months, default=months)
    ss = st.sidebar.multiselect("Customer state", states, default=states); sc = st.sidebar.multiselect("Category (first item of the order)", cats, default=cats)
    so = st.sidebar.multiselect("Order status", statuses, default=statuses)
    fo = o[o.purchase_year.isin(sy) & o.month_no.isin(sm) & o.customer_state.isin(ss) & o.category.isin(sc) & o.order_status.isin(so)]
    fi = items[items.order_id.isin(fo.order_id)]; fp = pays[pays.order_id.isin(fo.order_id)]
    st.sidebar.caption(f"{len(fo):,} of {len(o):,} orders selected")
    if fo.empty: st.warning("No orders match the filters.")
    else: DASH[PAGE](fo, fi, fp)
else: page_quality()
