# Online shop — notes

## পেজের সেকশন (হোম পেজ `/`)
Announcement bar → Header (logo, search, Login / Dashboard / Orders, Cart) → Hero banner → Trust strip
(delivery, payment, genuine products, support) → Shop by category → Special offers (discounted products) →
New arrivals → Popular right now (online orders থেকে) → All products (filter + sort) → About → Contact → Footer.
প্রডাক্ট ক্লিক করলে details modal। মোবাইলে নিচে ভাসমান "View cart" বার।

## অ্যাডমিন প্যানেল = আপনার inventory
- Menu → Online Shop → **Shop Settings**: দোকানের নাম, ট্যাগলাইন, ব্র্যান্ড কালার, announcement, ব্যানার ছবি/লেখা,
  About, যোগাযোগ (ফোন, WhatsApp, ইমেইল, ঠিকানা, সময়, Facebook), delivery charge, free delivery সীমা, অর্ডার চালু/বন্ধ।
- Menu → Online Shop → **Online Orders**: Pending → Confirm → Delivered / Cancel।
- প্রডাক্টের নাম, ছবি, দাম, ডিসকাউন্ট (`discount_*`), ক্যাটাগরি, বিবরণ, স্টক — সব আসে inventory র Product থেকেই।
  শপে শুধু active ও stock > 0 প্রডাক্ট দেখায়। ডিসকাউন্ট `Product.final_price` অনুযায়ী।

## রং ও ডার্ক/লাইট মোড
- ব্র্যান্ড রং: Shop Settings এর color picker (যেকোনো hex)। বাটন/ব্যাজের লেখা অটো সাদা বা গাঢ় হয় (উজ্জ্বলতা দেখে)।
  ডার্ক মোডে রং-লেখা অটো হালকা হয়, যাতে কালো ব্যাকগ্রাউন্ডে পড়া যায়। পেজের ছায়া/হালকা অংশ ব্র্যান্ড রং থেকেই তৈরি।
- মোড: "Default mode" = Auto (ভিজিটরের ডিভাইস) / Always light / Always dark। ভিজিটর হেডারের চাঁদ/সূর্য বাটনে বদলাতে পারে (মনে রাখা হয়)।

## Stock
- এক জায়গায় (`Product.stock_qty`)। অনলাইন অর্ডার দিলেই stock কমে (reserve), cancel করলে ফেরত। POS একই stock ব্যবহার করে।

## কোম্পানি
- এখন প্রথম active company। নির্দিষ্ট করতে settings এ `SHOP_COMPANY_ID = <id>`। `/shop/<company_id>/` ও কাজ করে।
- **Multi-company: ডোমেইন দিয়ে।** Shop Settings এ "Shop address" (যেমন `shop.meherin.com`) দিলে ওই ডোমেইনে ঢুকলে সেই কোম্পানির শপ দেখায়
  (`_company_for_request()` in shop/views.py)। ডোমেইন না মিললে: `SHOP_COMPANY_ID`, নাহলে মাত্র একটা active কোম্পানি থাকলে সেটা, নাহলে 404।
- ডোমেইন চালু করতে: ১) DNS এ ডোমেইনটা এই সার্ভারে পয়েন্ট করুন ২) `ALLOWED_HOSTS` এ যোগ করুন ৩) https হলে `CSRF_TRUSTED_ORIGINS` এ
  `https://shop.meherin.com` যোগ করুন ৪) Shop Settings এ ডোমেইন সেভ করুন।
- স্টাফ লগইন সেশন প্রতি ডোমেইনে আলাদা (cookie ডোমেইনভিত্তিক)। শপ ডোমেইনের Login বাটন সেই ডোমেইনেই লগইন করায়।

## TODO
1. Confirm এ অটো Sale / Customer / Money Receipt — `sales/models.py` লাগবে।
2. ডেস্কটপ অ্যাপ যদি আলাদা stock-movement রাখে, অনলাইন অর্ডারের stock পরিবর্তনও সেখানে লিখতে হবে।
3. পেমেন্ট এখন Cash on Delivery। অনলাইন পেমেন্ট (bKash/Nagad) পরে।
4. ক্যাটাগরির ছবি (Category এ image ফিল্ড নেই — এখন প্রথম অক্ষর দেখায়), রিভিউ, কুপন — পরে।

## বসানোর পর
`python manage.py makemigrations shop && python manage.py migrate`
