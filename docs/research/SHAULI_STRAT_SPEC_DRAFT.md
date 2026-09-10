# Shauli_strat — דוח אפיון אסטרטגיה (טיוטה לאישור)

**סטטוס:** טיוטת אפיון בלבד — לא מומשה בקוד, לא בוצע backtest, ולא שונו כללי AlphaPilot.  
**מקור:** התמונות שסופקו בשיחה.  
**שם האסטרטגיה לאחר אישור:** `Shauli_strat`

---

## 1. מטרת האסטרטגיה

`Shauli_strat` היא אסטרטגיית Price Action / Smart Money Concepts המבוססת על מבנה שוק, נזילות, Inducement, Liquidity Sweep/Stop Hunt, שינוי/המשך מבנה, ואזורי אי-יעילות/עניין לצורך כניסה.

הרעיון המרכזי אינו “לקנות כי המחיר עולה” או “למכור כי המחיר יורד”, אלא:

1. לזהות את כיוון ומבנה השוק.
2. למפות היכן יושבת נזילות.
3. לזהות פיתוי/Inducement שמושך סוחרים למיקום צפוי.
4. להמתין ללקיחת הנזילות.
5. לדרוש אישור מבני לכך שהמהלך האמיתי מתחיל.
6. להיכנס מאזור איכותי לאחר האישור.
7. למקם invalidation/Stop מעבר לנקודה שמבטלת את תזת העסקה.
8. לכוון לנזילות בצד הנגדי.

---

## 2. עקרונות יסוד

### 2.1 Market Structure

האסטרטגיה קוראת את השוק כרצף של Swing High ו-Swing Low.

**מבנה שורי:**
- Higher High (HH)
- Higher Low (HL)
- המשך שבירת שיאים בכיוון מעלה.

**מבנה דובי:**
- Lower Low (LL)
- Lower High (LH)
- המשך שבירת שפלים בכיוון מטה.

המבנה משמש להגדרת bias, לזיהוי המשך, ולזיהוי הרגע שבו שליטה עוברת מצד אחד לצד השני.

---

## 3. Liquidity — נזילות

האסטרטגיה מניחה שמעל שיאים ומתחת לשפלים מצטברים Stop Orders ופקודות ממתינות.

### BSLQ — Buy-Side Liquidity
נזילות הנמצאת מעל:
- Swing High;
- Equal Highs;
- שיא ברור שהשוק יכול למשוך אליו מחיר.

### SSLQ — Sell-Side Liquidity
נזילות הנמצאת מתחת:
- Swing Low;
- Equal Lows;
- שפל ברור שהשוק יכול למשוך אליו מחיר.

נזילות אינה Entry בפני עצמה. היא יעד פוטנציאלי של המחיר ומרכיב בהבנת התרחיש.

---

## 4. Inducement — אינדוסמנט

Inducement הוא מנגנון שבו השוק יוצר מבנה שנראה כמו הזדמנות ברורה או שינוי/פריצה, ובכך מושך סוחרים להיכנס מוקדם.

לאחר שהסוחרים נכנסו:
- הסטופים שלהם הופכים לנזילות;
- המחיר יכול לחזור לקחת את הנזילות;
- ורק לאחר מכן להמשיך במהלך האמיתי.

לכן `Shauli_strat` אינה אמורה להיכנס על כל breakout ראשון.

העיקרון הוא:

```text
מבנה שנראה ברור
    ↓
כניסת סוחרים מוקדמת
    ↓
נוצר מאגר Stop/Liquidity
    ↓
Liquidity Sweep / Stop Hunt
    ↓
אישור מבני
    ↓
המהלך האמיתי
```

בתרחיש שורי נחפש לרוב Inducement/SSLQ מתחת למבנה לפני עלייה.

בתרחיש דובי נחפש לרוב Inducement/BSLQ מעל למבנה לפני ירידה.

---

## 5. Liquidity Sweep / Stop Hunt

Sweep הוא מצב שבו המחיר חודר מעבר לרמת נזילות ברורה, לוקח את הסטופים/הפקודות, אך אינו ממשיך בהכרח בכיוון הפריצה.

ה-Sweep משמעותי כאשר הוא משתלב עם ההקשר המבני.

### Sweep שורי
- המחיר יורד מתחת ל-SSLQ;
- לוקח נזילות;
- חוזר מעל האזור;
- מופיע אישור לשינוי/המשך שורי.

### Sweep דובי
- המחיר עולה מעל BSLQ;
- לוקח נזילות;
- חוזר מטה;
- מופיע אישור לשינוי/המשך דובי.

פריצה של נזילות ללא חזרה/אישור אינה מספיקה בפני עצמה.

---

## 6. BOS — Break of Structure

BOS משמש בעיקר כאישור המשך בכיוון מבנה קיים.

**Bullish BOS:** שבירה מאושרת של Swing High רלוונטי בכיוון השורי.

**Bearish BOS:** שבירה מאושרת של Swing Low רלוונטי בכיוון הדובי.

ה-BOS חייב להיות מוגדר על Swing מבני אמיתי, ולא על כל High/Low קטן.

---

## 7. CHOCH / Market Structure Shift

CHOCH (Change of Character) / שינוי אופי השוק הוא השבירה הראשונה המשמעותית נגד המבנה הקודם ויכול לשמש כאישור לכך שהשליטה עוברת לצד השני.

**Bullish CHOCH:**
לאחר מהלך דובי / Sweep של SSLQ, המחיר שובר מבנה קצר-טווח כלפי מעלה.

**Bearish CHOCH:**
לאחר מהלך שורי / Sweep של BSLQ, המחיר שובר מבנה קצר-טווח כלפי מטה.

במודל הכניסה של Shauli_strat, Sweep ללא CHOCH/BOS מתאים הוא אירוע נזילות — לא Entry מאושר.

---

## 8. Displacement

לאחר לקיחת נזילות ושינוי מבנה, נרצה לראות תנועה אימפולסיבית בכיוון החדש.

Displacement איכותי:
- מתקדם במהירות יחסית;
- שובר מבנה;
- משאיר אי-יעילות;
- מעיד על חוסר איזון ברור בין קונים למוכרים.

Displacement מחזק את ההנחה שה-Sweep היה לקיחת נזילות ולא breakout אמיתי בכיוון הנגדי.

---

## 9. FVG / Imbalance

Fair Value Gap הוא אזור אי-יעילות שנוצר בתנועה אימפולסיבית.

במודל של שלושה נרות, קיים אזור מחיר שלא קיבל חפיפה מלאה בין הקצוות של נר 1 ונר 3.

ה-FVG משמש:
- אזור Retracement;
- אזור שבו ניתן לחפש Entry לאחר אישור;
- confluence עם Order Block / Structure / Liquidity.

FVG אינו אות עצמאי.

```text
Sweep
  ↓
CHOCH/BOS
  ↓
Displacement
  ↓
FVG נוצר
  ↓
Retrace אל FVG
  ↓
Entry candidate
```

---

## 10. Order Block / POI

Order Block הוא אזור המקושר לנר/מבנה האחרון נגד כיוון ה-Displacement שהוביל לשבירת מבנה.

**Bullish Order Block:**
אזור ביקוש לפני displacement שורי.

**Bearish Order Block:**
אזור היצע לפני displacement דובי.

ה-OB משמש Point of Interest ולא אות אוטומטי.

איכות האזור עולה כאשר קיימת חפיפה בין:
- Liquidity Sweep;
- CHOCH/BOS;
- Displacement;
- FVG;
- Order Block;
- מיקום נכון בתוך ה-Dealing Range.

---

## 11. Premium / Discount / Dealing Range

כאשר מוגדר Range מבני בין Swing Low לבין Swing High:

- החצי העליון הוא Premium;
- החצי התחתון הוא Discount;
- האמצע הוא Equilibrium בקירוב.

רעיון העבודה:

**Long:** עדיפות לחיפוש קנייה ב-Discount כאשר ההקשר שורי.

**Short:** עדיפות לחיפוש מכירה ב-Premium כאשר ההקשר דובי.

Premium/Discount אינו מספיק לבדו לכניסה; הוא פילטר מיקום.

---

## 12. מודל LONG מלא

```text
1. Bias/Structure שורי או תנאים לשינוי שורי
        ↓
2. זיהוי SSLQ / שפל משמעותי / Inducement
        ↓
3. מחיר יורד ולוקח את ה-SSLQ
        ↓
4. Reclaim / דחייה מהאזור
        ↓
5. Bullish CHOCH / BOS
        ↓
6. Displacement שורי
        ↓
7. נוצר POI איכותי:
   FVG ו/או Bullish OB
        ↓
8. Retracement אל אזור הכניסה
        ↓
9. Entry LONG
        ↓
10. Invalidation/Stop מתחת לנזילות/מבנה המבטל
        ↓
11. Target לכיוון BSLQ / Swing High / נזילות נגדית
```

עסקת LONG אינה מאושרת רק משום שהמחיר לקח SSLQ. האישור המבני לאחר ה-Sweep הוא חלק מהמודל.

---

## 13. מודל SHORT מלא

```text
1. Bias/Structure דובי או תנאים לשינוי דובי
        ↓
2. זיהוי BSLQ / שיא משמעותי / Inducement
        ↓
3. מחיר עולה ולוקח את ה-BSLQ
        ↓
4. Reclaim / דחייה מהאזור
        ↓
5. Bearish CHOCH / BOS
        ↓
6. Displacement דובי
        ↓
7. נוצר POI איכותי:
   FVG ו/או Bearish OB
        ↓
8. Retracement אל אזור הכניסה
        ↓
9. Entry SHORT
        ↓
10. Invalidation/Stop מעל לנזילות/מבנה המבטל
        ↓
11. Target לכיוון SSLQ / Swing Low / נזילות נגדית
```

---

## 14. סדר עדיפויות ל-Entry

האסטרטגיה אינה אמורה לעבוד כ-"מצא OB וקנה".

הסדר הלוגי הוא:

```text
Context
→ Structure
→ Liquidity
→ Inducement
→ Sweep
→ Structural confirmation
→ Displacement
→ POI
→ Retracement
→ Entry
→ Invalidation
→ Opposing liquidity target
```

ככל שחסרות שכבות מרכזיות בתרחיש, איכות ה-setup יורדת.

---

## 15. מה לא נחשב Setup תקין

בשלב האפיון, Shauli_strat צריכה לדחות לפחות את המצבים הבאים:

- פריצה ללא Liquidity context;
- Sweep ללא אישור מבני;
- FVG ללא Sweep/Structure מתאים;
- Order Block אקראי שלא הוביל ל-Displacement/Structure break;
- כניסה באמצע Range ללא יתרון מיקום ברור;
- כניסה לאחר שהמחיר כבר התרחק משמעותית מה-POI;
- Long ישירות אל BSLQ קרוב מאוד ללא מרווח;
- Short ישירות אל SSLQ קרוב מאוד ללא מרווח;
- Trade שבו לא ניתן להגדיר Invalidation לפני הכניסה.

---

## 16. Stop / Invalidation

בניגוד ל-EMA20, ב-Shauli_strat יש היגיון טבעי ל-Structural Invalidation.

### Long
ה-Stop צריך להיות מעבר לנקודה שאם המחיר חוזר דרכה, תזת ה-Sweep והשינוי השורי כבר אינה תקפה.

מועמדים מבניים:
- מתחת ל-Sweep Low;
- מתחת ל-Bullish OB / POI, בהתאם להגדרה שתוקפא.

### Short
- מעל ל-Sweep High;
- מעל ל-Bearish OB / POI, בהתאם להגדרה שתוקפא.

**חשוב:** התמונות מגדירות את הרעיון המבני, אך אינן מספיקות לקבוע כרגע buffer מספרי, slippage או מרחק מינימלי/מקסימלי ל-Stop. אלו חייבים להיקבע לפני backtest.

---

## 17. Take Profit

יעד טבעי של המודל הוא נזילות נגדית.

### Long
יעדים אפשריים לפי מבנה:
- Internal BSLQ;
- Swing High;
- External BSLQ.

### Short
- Internal SSLQ;
- Swing Low;
- External SSLQ.

אין עדיין כלל מאושר מהתמונות לגבי:
- TP יחיד או חלקי;
- מינימום R:R;
- העברה ל-Breakeven;
- trailing;
- יציאה חלקית.

לכן אסור להמציא אותם בזמן המימוש.

---

## 18. State Machine מוצע למימוש עתידי

לאחר אישור הדוח, מומלץ שהאסטרטגיה תיוצג כמכונת מצבים מפורשת:

```text
IDLE
 ↓
CONTEXT_IDENTIFIED
 ↓
LIQUIDITY_MAPPED
 ↓
INDUCEMENT_IDENTIFIED
 ↓
LIQUIDITY_SWEPT
 ↓
STRUCTURE_CONFIRMED
 ↓
DISPLACEMENT_CONFIRMED
 ↓
POI_READY
 ↓
WAITING_FOR_RETRACE
 ↓
ENTRY_READY
 ↓
IN_POSITION
 ↓
TARGET_HIT / INVALIDATED
```

כל מעבר חייב להיות deterministic וניתן להסבר.

---

## 19. עובדות שהמערכת צריכה להחזיר לכל Setup

לצורך auditability:

- direction: LONG / SHORT;
- higher-level bias;
- current structure;
- relevant swing high/low;
- BSLQ;
- SSLQ;
- inducement level;
- sweep level;
- sweep timestamp;
- CHOCH/BOS level;
- structural-confirmation timestamp;
- displacement status;
- FVG bounds;
- Order Block bounds;
- selected POI;
- entry price/zone;
- stop/invalidation;
- target liquidity;
- setup state;
- rejection reason;
- strategy version.

---

## 20. Reason Codes מוצעים

```text
NO_VALID_STRUCTURE
NO_LIQUIDITY_TARGET
NO_INDUCEMENT
WAITING_FOR_LIQUIDITY_SWEEP
SWEEP_NOT_CONFIRMED
NO_STRUCTURE_SHIFT
NO_DISPLACEMENT
NO_VALID_FVG
NO_VALID_ORDER_BLOCK
NO_VALID_POI
WAITING_FOR_RETRACE
ENTRY_TOO_EXTENDED_FROM_POI
INVALID_STOP_GEOMETRY
INSUFFICIENT_ROOM_TO_TARGET
SETUP_READY
LONG_READY
SHORT_READY
```

השמות הסופיים יותאמו ל-conventions של AlphaPilot בזמן המימוש.

---

## 21. כללי No-Lookahead ל-Backtest

המימוש חייב להשתמש רק במידע שהיה ידוע בזמן ההחלטה.

לכן:

- Swing אינו יכול להפוך ל-"confirmed" באמצעות נרות עתידיים בלי להוסיף את זמן האישור בפועל.
- CHOCH/BOS חייבים להיות ידועים רק לאחר שה-break התקיים לפי ההגדרה שנקפיא.
- FVG נוצר רק לאחר שהנר השלישי הרלוונטי קיים.
- Order Block לא יקבל תוקף בדיעבד לפני ה-Displacement/Break שמגדיר אותו.
- Sweep לא יוכר לפני שהמחיר באמת נסחר מעבר לרמת הנזילות.
- Entry אינו רשאי להשתמש ב-High/Low עתידי של אותו נר כדי לבחור fill מושלם.
- Stop ו-Target חייבים להיות ידועים לפני ביצוע העסקה.

---

## 22. נושאים שהתמונות עדיין לא קובעות באופן מספרי

לפני שנכתוב קוד או נריץ מחקר, יש להקפיא במפורש את הפרטים הבאים:

1. **Timeframes** — באיזה TF קובעים Bias ובאיזה TF מחפשים Entry.
2. **Swing algorithm** — כמה נרות משמאל/ימין נדרשים ל-Swing מאושר.
3. **Equal High/Low tolerance** — מה נחשב EQH/EQL.
4. **BOS definition** — Wick break או Close break.
5. **CHOCH definition** — Wick או Close, ואיזה Swing בדיוק חייב להישבר.
6. **Sweep confirmation** — האם Wick מעבר + Close חזרה מספיקים.
7. **Displacement threshold** — איך מגדירים displacement בצורה מספרית.
8. **FVG minimum size** — האם כל gap תקף או רק gap מינימלי.
9. **FVG entry point** — first touch, midpoint, full zone או כלל אחר.
10. **Order Block definition** — candle body/wick, last opposite candle, וכיצד zone נבנה.
11. **POI precedence** — מה קורה כאשר OB ו-FVG אינם חופפים.
12. **Premium/Discount** — איזה Swing Range הוא ה-Dealing Range.
13. **Stop buffer** — מעבר ל-Sweep/OB בכמה בדיוק.
14. **Target hierarchy** — internal liquidity לעומת external liquidity.
15. **Minimum reward-to-risk**, אם נדרש.
16. **Partial exits / breakeven / trailing**, אם קיימים.
17. **Session filter** — האם עובדים רק בשעות/סשנים מסוימים.
18. **Asset universe** — S&P 500 בלבד, מניות אמריקאיות, Forex, או כל שוק.
19. **Long/Short** — האם AlphaPilot יממש את שני הכיוונים או Long בלבד בשלב הראשון.
20. **Entry timing** — באותו bar, ב-bar הבא, limit zone, או confirmation candle.

הפרטים האלה אינם "פרטים קטנים": הם אלה שהופכים רעיון חזותי לאסטרטגיה דטרמיניסטית שניתן לבדוק בלי parameter fishing.

---

## 23. עקרונות מחקר ל-Shauli_strat

לאחר אישור המפרט:

- נכתוב Protocol לפני תוצאות.
- נקפיא V1 אחד בלבד.
- לא נבצע parameter sweep כדי למצוא גרסה מרוויחה.
- Development ו-Validation יהיו מופרדים.
- לא נשנה חוקים אחרי שראינו Validation.
- נשמור כל Setup עם provenance מלא.
- נמדוד גם rejected setups, לא רק trades.
- נפריד בין detection accuracy לבין portfolio performance.
- לא נקרא לאסטרטגיה production-ready ללא evidence מתאים.

---

## 24. מדדי Backtest נדרשים

כאשר Shauli_strat תמומש, הדוח צריך לכלול לפחות:

- setup count;
- entry count;
- rejection counts by reason;
- long/short split;
- win rate;
- average/median trade;
- average winner/loser;
- profit factor;
- expectancy;
- net return;
- CAGR;
- maximum drawdown;
- Sharpe/Calmar לפי conventions קיימים;
- turnover;
- transaction friction;
- average risk %;
- worst trade;
- MFE/MAE;
- R-multiple distribution;
- time in trade;
- setup type attribution;
- liquidity type attribution;
- OB/FVG confluence attribution;
- fold stability;
- validation performance.

---

## 25. הגדרת V1 ברמת קונספט

```text
Strategy:
Shauli_strat

Family:
Liquidity / Market Structure / SMC

Core thesis:
Wait for liquidity to be engineered and swept before entering in the
structurally confirmed direction.

Required high-level sequence:

LIQUIDITY
→ INDUCEMENT
→ SWEEP
→ CHOCH/BOS
→ DISPLACEMENT
→ POI (FVG / OB)
→ RETRACE
→ ENTRY
→ STRUCTURAL INVALIDATION
→ OPPOSING LIQUIDITY TARGET
```

---

## 26. סטטוס אישור

### מאושר עקרונית מתוך התמונות
- Market Structure;
- BSLQ / SSLQ;
- Inducement;
- Stop Hunt / Liquidity Sweep;
- BOS;
- CHOCH / structural shift;
- Displacement;
- FVG / imbalance;
- Order Block / POI;
- Premium / Discount context;
- entry after confirmation rather than blind breakout;
- structural invalidation;
- opposing liquidity as target concept.

### טרם מאושר מספרית
כל הפרמטרים שבסעיף 22.

---

## 27. תנאי מעבר למימוש

לא מתחילים implementation של `Shauli_strat` עד שהמשתמש:

1. מאשר שהדוח מייצג נכון את האסטרטגיה;
2. מתקן כל פרשנות שאינה תואמת את התמונות;
3. מאשר/מגדיר את החוקים המספריים החסרים;
4. מאשר Protocol V1 קפוא.

רק לאחר מכן ניצור Strategy חדשה, tests, backtesting protocol ו-integration ל-AlphaPilot.
