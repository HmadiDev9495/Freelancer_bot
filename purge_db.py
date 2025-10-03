# purge.py
from Main import purge_all_data

if __name__ == "__main__":
    print("⚠️ هشدار: تمام داده‌های کاربران پاک خواهند شد!")
    confirm = input("آیا مطمئن هستید؟ (yes/no): ").strip().lower()
    if confirm == "yes":
        success = purge_all_data()
        if success:
            print("✅ پاک‌سازی با موفقیت انجام شد.")
        else:
            print("❌ پاک‌سازی با خطا مواجه شد (جزئیات در لاگ).")
    else:
        print("❌ عملیات لغو شد.")