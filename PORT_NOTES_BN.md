# সিঙ্গেল ভার্সন থেকে মাল্টি-কোম্পানিতে আনা ফিচার (অনলাইন শপ বাদ, ব্যাচ/মেয়াদ বাদ)

## যা যোগ / ঠিক হয়েছে (সবই নিজের company অনুযায়ী আলাদা)
- সেল মোড: ফ্ল্যাট (প্যাক) দাম × পরিমাণ ঠিক, মোডের নিজস্ব ছাড়, `show_in_webapp` ("Sold by" এ দেখাবে কিনা), Sale/POS এ "Sold by"
- সেল রিটার্নে সেল মোড (২ × ২৫০ গ্রাম ফেরত = স্টকে +৫০০ গ্রাম)
- Short Sale পেজ, Due Reminders (WhatsApp / SMS লিংক), Low Stock Alert, Dashboard ট্রেন্ড চার্ট
- রিপোর্ট Excel / PDF Export (`/api/reports/export/<key>/?fmt=xlsx|pdf`)
- রিপোর্টের লাভ/পরিমাণের হিসাব সেল মোড অনুযায়ী (Top Products, Dashboard, Sales Report)
- পেজ গাইড, Light/Dark থিম, ক্রয়/রিটার্ন তালিকায় ইউনিটের নাম

## বসানোর ক্রম
    pip install -r requirements.txt        # openpyxl, reportlab
    # আগে database backup নিন
    python manage.py migrate               # products 0003, returns 0003
    python manage.py collectstatic --noinput
    touch tmp/restart.txt                  # cPanel restart
    # ব্রাউজারে Ctrl+F5

## সীমা
- Django এখানে চালানো হয়নি, শুধু Python syntax যাচাই। আগে ডেমো/কপি ডাটাবেসে চালান।
- Due Reminders এ দোকানের ফোন নেওয়া হয় company.phone থেকে (company তে আলাদা WhatsApp ফিল্ড নেই)।
- ব্যাচ/মেয়াদ (FEFO) এখনো আনা হয়নি।
