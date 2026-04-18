# سكربت العرض التقديمي – نظام حجز وتخصيص المخزون

## هدف العرض
هذا الملف يوجّهك خطوة بخطوة من لحظة فتح أودو على Odoo.sh إلى تنفيذ السيناريو الكامل المطلوب في المهمة من داخل الواجهة.

الفكرة الأساسية التي سنعرضها:
- حجز المخزون بشكل استباقي قبل التنفيذ الفعلي
- التخصيص حسب FEFO أو FIFO
- دعم التخصيص الجزئي وعدم توفر المخزون
- إنشاء حركات مخزون وتحويلات داخلية
- توفير API مع حماية بواسطة Token
- إظهار الجوانب الهندسية مثل الأداء والاختبارات والتزامن

---

## الشخصيات المستخدمة في العرض
أنشئ مستخدمين حتى يكون العرض واضحًا:

1. مستخدم الحجز
   - مثال: Demo Reservation User
   - الصلاحيات:
     - Internal User
     - Inventory / User
     - Stock Reservation User

2. مدير الحجز
   - مثال: Demo Reservation Manager
   - الصلاحيات:
     - Internal User
     - Inventory / Administrator
     - Stock Reservation Manager

واستخدم منتجًا قابلًا للتخزين مع متغيرات.

مثال مناسب:
- اسم المنتج: Antibiotic Kit
- المتغيرات: 250mg و 500mg
- التتبع: By Lots
- تواريخ الصلاحية: مفعلة

---

## مقدمة يمكنك قولها في البداية
اليوم سأعرض موديول مخصص داخل أودو يضيف نظام حجز وتخصيص ذكي للمخزون. الفكرة التجارية هنا هي تأمين الكميات المطلوبة مبكرًا قبل الشحن أو التنفيذ، خصوصًا عندما يكون هناك أكثر من طلب أو قناة تنافس على نفس المخزون.

---

## الجزء 1 – فتح أودو على Odoo.sh

### ماذا أفعل
1. افتح مشروع Odoo.sh.
2. افتح بيئة الفرع المطلوب.
3. اضغط Open Odoo.
4. ادخل بحساب المدير.

### ماذا أقول
أنا أبدأ من بيئة Odoo.sh حتى أوضح أن الحل منشور ويعمل داخل بيئة استضافة واقعية.

---

## الجزء 2 – تثبيت الموديول

### مسار القائمة
Apps → ابحث عن Stock Reservation Engine → Install

### ماذا أفعل
1. افتح شاشة Apps.
2. ابحث عن Stock Reservation Engine.
3. اضغط Install.

### ماذا أقول
هذا الموديول يوسّع تطبيق المخزون بإضافة دورة عمل لحجز المخزون، محرك تخصيص، واجهات API، شاشة Dashboard، وصلاحيات حسب الأدوار.

### المتطلب الذي نغطيه
- Build a working module
- UI integration inside Inventory

---

## الجزء 3 – إنشاء المستخدمين والصلاحيات

### مسار القائمة
Settings → Users & Companies → Users

### ماذا أفعل
1. أنشئ مستخدم باسم Demo Reservation User.
2. أعطه مجموعة Stock Reservation User.
3. أنشئ مستخدم باسم Demo Reservation Manager.
4. أعطه مجموعة Stock Reservation Manager.

### ماذا أقول
هذه الخطوة تحقق متطلب الأمان. المستخدم العادي يرى حجوزاته فقط، بينما المدير يمكنه رؤية كل الحجوزات وإدارة API Tokens.

### المتطلب الذي نغطيه
- Security
- Access restriction by role

---

## الجزء 4 – إعدادات المخزون اللازمة قبل العرض

### مسار القائمة
Inventory → Configuration → Settings

### فعّل هذه الخيارات
- Storage Locations
- Lots & Serial Numbers
- Expiration Dates
- Multi-Step Routes إذا أردت عرض تحويلات داخلية بشكل أوضح

### ماذا أقول
هذه الإعدادات مهمة لأن محرك التخصيص يعتمد على المواقع والمواقع الفرعية واللوتات التي تحتوي على تاريخ صلاحية. إذا وجد تاريخ صلاحية يطبق FEFO، وإذا لم يوجد يرجع إلى FIFO.

### المتطلب الذي نغطيه
- FEFO if lots with expiry exist
- FIFO otherwise
- Respect selected location and child locations

---

## الجزء 5 – إنشاء المنتج والمتغيرات

### مسار القائمة
Inventory → Products → Products

### ماذا أفعل
1. أنشئ منتجًا جديدًا باسم Antibiotic Kit.
2. اجعل النوع Storable Product.
3. فعل التتبع By Lots.
4. أضف Attribute مثل Strength بقيمتين 250mg و 500mg.
5. احفظ المنتج.

### ثم اعرض المتغيرات
مسار القائمة:
Inventory → Products → Product Variants

### ماذا أقول
أنا هنا أنشئ Product Template له Variants لأن سطر الحجز فعليًا يرتبط بالمنتج المتغير نفسه. وهذا يعكس الاستخدام الواقعي في المخزون.

### المتطلب الذي نغطيه
- Reservation lines linked to product variants through product_id

---

## الجزء 6 – إضافة المخزون واللوتات وتواريخ الصلاحية

### المسار المقترح
Inventory → Products → Product Variants → افتح متغيرًا → On Hand أو Update Quantity

### ماذا أفعل
لمتغير 250mg:
1. أضف كمية داخل WH/Stock.
2. استخدم لوتين مثل:
   - LOT-250-A بتاريخ صلاحية أقرب
   - LOT-250-B بتاريخ صلاحية أبعد
3. تأكد أن كلا اللوتين فيهما كميات متاحة.

### شاشة اختيارية للمراجعة
Inventory → Products → Lots/Serial Numbers

### ماذا أقول
هذا هو الإعداد الأساسي لإثبات FEFO. بما أن المنتج يتتبع باللوت ومعه تواريخ صلاحية، فيجب أن يختار النظام اللوت الأقرب انتهاءً أولًا.

---

## الجزء 7 – عرض القوائم المخصصة داخل المخزون

### مسار القائمة الرئيسي
Inventory → Stock Reservations

### اعرض هذه الشاشات
1. Dashboard
2. Reservation Batches
3. API Tokens

### ماذا أقول
الموديول مدمج مباشرة داخل تطبيق Inventory. والآن سأمر على كل شاشة من الشاشات المضافة.

---

## الجزء 8 – شاشة Dashboard

### مسار القائمة
Inventory → Stock Reservations → Dashboard

### ما الذي يظهر في الشاشة
- Graph view
- Pivot view
- Filters:
  - Allocated
  - Partial
  - Not Available
- Group By:
  - Product
  - State

### ماذا أقول
هذه الشاشة تعطي رؤية تحليلية لنتائج الحجز: ما الذي تم تخصيصه بالكامل، ما الذي خصص جزئيًا، وأين توجد حالات نقص.

### المتطلب الذي نغطيه
- UI enhancement
- Reporting visibility as a bonus item

---

## الجزء 9 – شاشة Reservation Batches

### مسار القائمة
Inventory → Stock Reservations → Reservation Batches

### ما الذي يظهر في القائمة
- Name
- Request User
- State
- Priority
- Scheduled Date
- Stock Moves count
- Transfers count

### ماذا أقول
هذه هي الشاشة الأساسية للمهمة. كل طلب حجز يتم تجميعه داخل Batch، وداخل كل Batch توجد Lines تمثل المنتجات والكميات المطلوبة.

### المتطلب الذي نغطيه
- Custom model: stock.reservation.batch
- Tree view

---

## الجزء 10 – السيناريو الأول: تخصيص كامل مع FEFO

### مسار الشاشة
Inventory → Stock Reservations → Reservation Batches → Create

### ماذا أفعل داخل الفورم
1. افتح فورم جديد من Reservation Batch.
2. تأكد أن Request User صحيح.
3. اجعل Priority مساوية High أو Urgent.
4. حدد Scheduled Date.
5. داخل تبويب Lines أضف سطرًا فيه:
   - Product: Antibiotic Kit, 250mg variant
   - Requested Qty: 6
   - Location: WH/Stock
6. احفظ.
7. اضغط Confirm.
8. اضغط Allocate.

### ماذا أُظهر بعد التخصيص
- حقل Allocated Qty يتم تحديثه
- State في السطر تصبح Allocated إذا كانت الكمية كافية
- اللوت المختار يظهر تلقائيًا عند الحاجة
- حالة الـ Batch تصبح Allocated
- يظهر Smart Button باسم Stock Moves
- يظهر Smart Button باسم Transfers

### ماذا أقول
هنا أنا أعرض التدفق الأساسي للحل. المستخدم ينشئ حجزًا مسبقًا قبل التنفيذ. وعند الضغط على Allocate يقوم النظام بالقراءة من stock.quant ويطبق FEFO لأن لدينا لوتات بتاريخ صلاحية، ثم ينشئ حركات مخزون بالكميات المخصصة.

### المتطلب الذي نغطيه
- Allocation engine
- FEFO logic
- allocated_qty update
- state update
- stock.move generation
- smart buttons for related records

---

## الجزء 11 – عرض حركة المخزون والتحويل الداخلي

### من داخل فورم الـ Batch
اضغط على Smart Button: Stock Moves

### ثم
اضغط على Smart Button: Transfers

### ماذا أقول
المتطلب طلب إنشاء stock.move بعد التخصيص وربط الحركة بسطر الحجز. والواجهة هنا تثبت أن الحركة والتحويل الداخلي قد تم إنشاؤهما بنجاح.

### المتطلب الذي نغطيه
- Stock integration
- View related moves through UI

---

## الجزء 12 – السيناريو الثاني: تخصيص جزئي

### مسار الشاشة
Inventory → Stock Reservations → Reservation Batches → Create

### ماذا أفعل
1. أنشئ Batch جديدة لنفس المتغير.
2. اطلب كمية أكبر من المتوفر، مثل 20.
3. احفظ ثم Confirm ثم Allocate.

### ماذا أُظهر
- Allocated Qty أقل من Requested Qty
- حالة السطر تصبح Partial
- حالة الـ Batch تصبح Partial

### ماذا أقول
هذا يثبت أن الحل يدعم التخصيص الجزئي بدل أن يفشل بالكامل. وهذا مهم جدًا في البيئات التي يوجد فيها ضغط على المخزون.

### المتطلب الذي نغطيه
- Partial allocation
- predictable shortage handling

---

## الجزء 13 – السيناريو الثالث: عدم توفر مخزون

### التحضير
أنشئ متغيرًا آخر أو استخدم منتجًا بدون كمية متاحة.

### مسار الشاشة
Inventory → Stock Reservations → Reservation Batches → Create

### ماذا أفعل
1. أضف سطرًا لمنتج لا يملك On Hand quantity.
2. احفظ ثم Confirm ثم Allocate.

### ماذا أُظهر
- Allocated Qty تبقى 0
- State تصبح Not Available
- لا يتم إنشاء حركة مخزون
- Batch تنتهي بحالة Partial لأن الطلب لم يُلبَّ بالكامل

### ماذا أقول
هذا يغطي حالة عدم توفر المخزون المطلوبة في المهمة ويعطي سلوكًا واضحًا ومفهومًا للمستخدم.

### المتطلب الذي نغطيه
- No stock scenario
- clear state management

---

## الجزء 14 – عرض سلوك الصلاحيات

### ماذا أفعل
1. ادخل بحساب Demo Reservation User.
2. افتح Inventory → Stock Reservations → Reservation Batches.
3. اعرض أن هذا المستخدم يرى سجلاته فقط.
4. ثم ادخل بحساب Demo Reservation Manager.
5. اعرض أن المدير يرى كل الحجوزات وشاشة API Tokens أيضًا.

### ماذا أقول
قواعد الأمان هنا تطبق عزلًا للبيانات للمستخدمين العاديين، بينما يحصل المدير على صلاحيات أوسع للمراجعة والدعم والتشغيل.

### المتطلب الذي نغطيه
- Users can only access their own reservations
- Managers can access all
- Allocation restricted by authorization

---

## الجزء 15 – شاشة API Tokens

### مسار القائمة
Inventory → Stock Reservations → API Tokens

### ملاحظة مهمة
هذه الشاشة تظهر للمدير.

### ماذا أفعل
1. أنشئ Token لمستخدم معين.
2. احفظه.

### ماذا أقول
الموديول يوفّر Token-based authentication حتى تستطيع أنظمة خارجية مثل Marketplace أو POS أو Procurement Engine أن تتكامل معه بشكل آمن.

### المتطلب الذي نغطيه
- Token-based API authentication

---

## الجزء 16 – عرض سيناريو الـ API

### الـ Endpoints التي تذكرها
- POST /api/reservation/create
- POST /api/reservation/allocate
- GET /api/reservation/status/<id>

### ماذا أقول أثناء العرض باستخدام Postman أو curl
أولًا النظام الخارجي يرسل طلب create فيه المنتج والكمية والموقع. بعد ذلك يرسل allocate. ثم يقرأ status ليرى حالة الحجز، الكمية المخصصة، والـ move المرتبط بصيغة JSON واضحة.

### نقاط مهم تذكرها
- request/response structure نظيف
- توجد رسائل خطأ واضحة للحالات غير المصرح بها أو البيانات غير الصحيحة
- هذا يجعل الحل جاهزًا للتكامل مع أنظمة خارجية

### المتطلب الذي نغطيه
- API layer
- proper error handling
- clean JSON structure

---

## الجزء 17 – ربط العرض بنص المهمة الأصلي

### 1. Custom Models
تم عرضها في شاشة Reservation Batches والـ Lines الموجودة داخل الفورم.

### 2. Allocation Engine
تم عرضه من خلال زر Allocate وتحديث الكميات والحالات باستخدام FEFO أو FIFO.

### 3. Stock Integration
تم عرضه من خلال Smart Buttons: Stock Moves و Transfers.

### 4. API Layer
تم عرضه من خلال شاشة API Tokens والـ Endpoints الثلاثة.

### 5. UI
تم عرضه من خلال List View و Form View و Smart Buttons و Dashboard.

### 6. Security
تم عرضه من خلال الفرق بين صلاحيات المستخدم العادي والمدير.

---

## الجزء 18 – الإغلاق الهندسي للمهمة

في نهاية العرض قل باختصار:

هذا التسليم لا يركّز فقط على الوظيفة، بل يشمل أيضًا التفكير الهندسي: خطة Sprint لثلاثة أيام، اختبارات تغطي التخصيص الكامل والجزئي وعدم توفر المخزون، وعي بالأداء والاستعلامات المهمة، قيود وفهارس على قاعدة البيانات، والانتباه لمشكلة التزامن بين المستخدمين.

### نقاط مختصرة تذكرها
- توجد Sprint breakdown لثلاثة أيام
- توجد اختبارات على منطق التخصيص والـ API
- توجد indexes و SQL constraints على الحقول المهمة
- توجد concurrency awareness مع lock-aware allocation
- توجد logging و timing لفهم الأداء

### المتطلب الذي نغطيه
- Sprint Delivery Simulation
- Testing
- Performance Validation
- Database Design & Tuning
- Concurrency Awareness

---

## خاتمة قصيرة يمكنك قولها
باختصار، هذا الموديول يضيف دورة عمل استباقية لحجز المخزون داخل أودو، ويدعم المستخدمين من خلال الواجهة، ويدعم الأنظمة الخارجية من خلال API آمن، ويعطي موثوقية تشغيلية من خلال التخصيص المنضبط والممارسات الهندسية الجيدة.

---

## نسخة مختصرة جدًا لعرض سريع في 10 دقائق
إذا احتجت نسخة سريعة في المقابلة اتبع هذا التسلسل:

1. افتح Odoo.sh وسجل الدخول
2. ثبّت الموديول
3. اعرض إعدادات Inventory
4. أنشئ منتجًا متتبعًا باللوت وله Variants
5. أضف كميات مع تواريخ صلاحية
6. افتح Inventory → Stock Reservations → Reservation Batches
7. أنشئ Batch فيها Full Allocation
8. أنشئ Batch فيها Partial Allocation
9. اعرض Stock Moves و Transfers
10. اعرض Dashboard و API Tokens
11. اختم بالاختبارات والأداء وقاعدة البيانات والتزامن
