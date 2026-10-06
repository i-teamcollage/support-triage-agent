"""The help centre of Hollinvale Home, a fictional online shop for furniture and home goods.

25 articles. Each has an id, a title, a section, the team that owns the topic, and the text a customer sees.
Every policy here is made up for this sample.
"""

ARTICLES = [
    {
        "id": "HC-01",
        "title": "Changing or cancelling an order",
        "section": "Orders",
        "team": "logistics",
        "body": "You can change or cancel an order yourself until it is packed. Go to My account > Orders, open the "
        "order and choose Change or Cancel. A cancellation is free of charge. Most orders are packed within 2 hours on "
        "working days, so please be quick.\n"
        "Once the status shows packed or shipped, the order can no longer be changed or cancelled. You can refuse "
        "the parcel when it arrives, or return it free of charge within 30 days of delivery (see How to return an "
        "item). Your refund then follows the usual refund timing.\n"
        "Orders paid by bank transfer are cancelled automatically if the payment has not arrived after 7 days.",
    },
    {
        "id": "HC-02",
        "title": "What your order status means",
        "section": "Orders",
        "team": "logistics",
        "body": "Received: we have your order and it is waiting to be packed.\n"
        "Packed: your items are packed and waiting for the carrier. Changes are no longer possible.\n"
        "Shipped: the carrier has your parcel. You get an email with the tracking number, and the expected "
        "delivery date appears in My account > Orders.\n"
        "Delayed: the carrier has reported a delay. The new expected delivery date is shown on the order page.\n"
        "Partly delivered: your order travels in more than one parcel and at least one has arrived.\n"
        "Delivered: the carrier has confirmed delivery.\n"
        "Return in progress: we are waiting for your return, or it has arrived and your refund is being prepared.\n"
        "Returned: everything you sent back has arrived and your refund has been issued.\n"
        "Cancelled: the order was cancelled and any payment has been refunded.",
    },
    {
        "id": "HC-03",
        "title": "Changing your delivery address",
        "section": "Orders",
        "team": "logistics",
        "body": "Before your order is packed, you can change the delivery address in My account > Orders > Change "
        "address.\n"
        "After a parcel has shipped with Veloway Parcel, you can redirect it to another address or a pickup point "
        "from the tracking page, free of charge, until it is out for delivery.\n"
        "Tramline Couriers express parcels cannot be redirected.\n"
        "Large items delivered by Brookhaul cannot be sent to a different address once they have left our "
        "warehouse. Contact us and we will see what is possible.",
    },
    {
        "id": "HC-04",
        "title": "Delivery times and costs",
        "section": "Delivery",
        "team": "logistics",
        "body": "How much delivery costs depends on the size of your order. "
        "Standard delivery with Veloway Parcel costs €4.95 and is free for orders over €75. It takes 2 to 4 "
        "working days to the Netherlands, Belgium and Luxembourg, 3 to 5 working days to Germany, France and "
        "Austria, and 4 to 7 working days to Ireland, Denmark, Spain and Italy.\n"
        "Express delivery with Tramline Couriers costs €9.95 and arrives the next working day in the Netherlands, "
        "Belgium and Germany when you order before 14:00.\n"
        "Large items such as sofas, beds, wardrobes and dining tables are delivered by Brookhaul two-person "
        "delivery for €39.00 per order, in 5 to 10 working days (see Two-person delivery for large items).\n"
        "Working days are Monday to Friday, excluding public holidays.",
    },
    {
        "id": "HC-05",
        "title": "Tracking your parcel",
        "section": "Delivery",
        "team": "logistics",
        "body": "When your order ships, we email you the carrier's name and a tracking number. You can also find both "
        "in My account > Orders.\n"
        "Veloway Parcel tracking numbers start with VW, Tramline Couriers numbers start with TC, and Brookhaul "
        "numbers start with BH.\n"
        "Tracking can take up to 24 hours to show the first scan. The expected delivery date on your order page is "
        "updated whenever the carrier reports a change.\n"
        "If your order travels in more than one parcel, each parcel has its own tracking number.",
    },
    {
        "id": "HC-06",
        "title": "Two-person delivery for large items",
        "section": "Delivery",
        "team": "logistics",
        "body": "Sofas, beds, wardrobes, dining tables and other items over 30 kg are delivered by Brookhaul, our "
        "two-person delivery partner. Delivery costs €39.00 per order.\n"
        "When your item reaches the local Brookhaul depot, Brookhaul sends you a text message to book a 4-hour "
        "delivery slot. The expected delivery date on your order page is the first day you can book.\n"
        "The crew carries the item to the room of your choice, unpacks it and takes the packaging away. Please "
        "measure doors and stairways before ordering.\n"
        "If you need to change your slot, use the link in Brookhaul's text message at least 24 hours before the "
        "slot.",
    },
    {
        "id": "HC-07",
        "title": "Missed deliveries and pickup points",
        "section": "Delivery",
        "team": "logistics",
        "body": "If you are not at home, Veloway Parcel tries again the next working day. After a second attempt, the "
        "parcel goes to your nearest Veloway pickup point, where it is kept for 7 days. You get an email with the "
        "address.\n"
        "Parcels that are not collected within 7 days come back to us, and we refund the order once they arrive, "
        "minus the delivery cost.\n"
        "Tramline Couriers make one attempt and then leave a card with instructions to rebook.",
    },
    {
        "id": "HC-08",
        "title": "Late or lost parcels",
        "section": "Delivery",
        "team": "logistics",
        "body": "Most parcels arrive on the expected delivery date shown in My account > Orders. Sometimes a carrier "
        "needs a day or two longer.\n"
        "If the expected delivery date has passed, or tracking shows no movement for 5 working days, contact us. "
        "Our logistics team opens an investigation with the carrier, which takes up to 10 working days.\n"
        "If the carrier confirms that the parcel is lost, we send a replacement or refund you in full, whichever "
        "you prefer.\n"
        "Please do not place a second order in the meantime.",
    },
    {
        "id": "HC-09",
        "title": "Countries we deliver to",
        "section": "Delivery",
        "team": "logistics",
        "body": "We deliver to the Netherlands, Belgium, Luxembourg, Germany, France, Austria, Ireland, Denmark, Spain "
        "and Italy.\n"
        "We do not deliver to other countries or to forwarding addresses.\n"
        "Large items are delivered by Brookhaul in all of these countries except Ireland, where we cannot deliver "
        "large items at the moment.\n"
        "Prices on our website include VAT for the country you deliver to.",
    },
    {
        "id": "HC-10",
        "title": "How to return an item",
        "section": "Returns and refunds",
        "team": "logistics",
        "body": "You can return most items within 30 days of delivery. Items must be unused and, where possible, in "
        "their original packaging.\n"
        "To start a return, go to My account > Orders, choose Return an item and select the items. For parcels, "
        "you get a free Veloway Parcel return label or a QR code to show at any Veloway pickup point.\n"
        "Large items are collected by Brookhaul. A collection costs €29.00, which is deducted from your refund. "
        "Brookhaul contacts you to agree on a date.\n"
        "The last day you can return items from an order is shown on the order page as the return window. Returns "
        "of parcels are free of charge.",
    },
    {
        "id": "HC-11",
        "title": "When you get your refund",
        "section": "Returns and refunds",
        "team": "billing",
        "body": "We refund you within 5 working days after your return arrives at our warehouse. You get an email "
        "when the refund is issued, and the status of your refund and the date we expect to issue it are shown on "
        "your order page.\n"
        "The refund goes back to the payment method you used. Banks and card issuers can take another 3 to 5 "
        "working days to show it on your statement.\n"
        "If you return the whole order within 30 days, we also refund the standard delivery cost. Two-person "
        "delivery costs are not refunded.\n"
        "For orders paid with Pay in 30 days, the open invoice is reduced instead of money being sent back.",
    },
    {
        "id": "HC-12",
        "title": "Items that cannot be returned",
        "section": "Returns and refunds",
        "team": "logistics",
        "body": "For hygiene and other reasons, we cannot take back:\n"
        "- made-to-measure curtains and blinds;\n"
        "- personalised or engraved items;\n"
        "- pillows, duvets, mattresses and mattress toppers once their protective wrapping is opened;\n"
        "- gift cards.\n"
        "This does not affect your rights when an item is damaged or faulty (see Damaged or faulty items).",
    },
    {
        "id": "HC-13",
        "title": "Damaged or faulty items",
        "section": "Returns and refunds",
        "team": "logistics",
        "body": "Please check your order when it arrives. If an item is damaged or faulty, report it within 14 days of "
        "delivery using the form in My account > Orders > Report a problem, with a photo of the damage and of the "
        "box.\n"
        "Our logistics team then offers a replacement, a spare part or a refund. You never pay for returning a "
        "damaged item.\n"
        "Please keep the item and its packaging until we have agreed on a solution.\n"
        "Faults that appear later are covered by our guarantee (see Guarantee and warranty claims).",
    },
    {
        "id": "HC-14",
        "title": "Missing items or parts",
        "section": "Returns and refunds",
        "team": "logistics",
        "body": "Orders with several items often travel in more than one parcel, sometimes on different days, so a "
        "partial delivery is normal. Check "
        "My account > Orders to see each parcel, its tracking number and its expected delivery date before "
        "reporting an item as missing.\n"
        "If a part is missing from a flat-pack item, find the part number in the assembly instructions and report "
        "it in My account > Orders > Report a problem. Missing parts are sent free of charge within 3 to 5 working "
        "days.",
    },
    {
        "id": "HC-15",
        "title": "Exchanges",
        "section": "Returns and refunds",
        "team": "logistics",
        "body": "We do not exchange items directly. If you would like a different size or colour, return the item "
        "(see How to return an item) and place a new order for the one you want. This way you get the new item as "
        "soon as possible, without waiting for the return to arrive.\n"
        "If you received a different item from the one you ordered, report it as a problem so that we can send the "
        "right one.",
    },
    {
        "id": "HC-16",
        "title": "Payment methods",
        "section": "Payments and invoices",
        "team": "billing",
        "body": "You can pay with:\n"
        "- credit or debit card;\n"
        "- bank transfer (SEPA): we ship your order once the payment has arrived, usually after 1 to 2 working "
        "days;\n"
        "- Pay in 30 days (see Pay in 30 days);\n"
        "- Hollinvale gift cards, also together with another payment method.\n"
        "All prices are in euros. Your card is charged when you place the order. If a payment fails, the order is "
        "not placed and no money is taken. A pending authorisation from a failed attempt disappears from your "
        "statement within 7 days.",
    },
    {
        "id": "HC-17",
        "title": "Pay in 30 days",
        "section": "Payments and invoices",
        "team": "billing",
        "body": "Pay in 30 days lets you pay later, after your order has shipped. It is available for orders from "
        "€20 up to €1,500 to addresses in the Netherlands, "
        "Belgium, Germany and Austria.\n"
        "You pay nothing at checkout. The invoice is due 30 days after your order ships; the due date is shown in "
        "My account > Orders.\n"
        "If the payment is late, we send a free reminder 7 days after the due date. A second reminder, 14 days "
        "after the due date, adds a €5.00 reminder fee.\n"
        "Returns reduce the amount you owe: you only pay for what you keep.",
    },
    {
        "id": "HC-18",
        "title": "Invoices and VAT receipts",
        "section": "Payments and invoices",
        "team": "billing",
        "body": "We email your VAT invoice, which is also your receipt, when your order ships. You can also download "
        "it at any time in My account > "
        "Orders > Invoice.\n"
        "If you buy for a business, enter your company name and VAT number at checkout, and they will appear on "
        "the invoice.\n"
        "Invoices cannot be edited once they are issued. If something on your invoice needs correcting, our billing "
        "team can issue a corrected invoice.",
    },
    {
        "id": "HC-19",
        "title": "Discount codes and gift cards",
        "section": "Payments and invoices",
        "team": "billing",
        "body": "Enter a discount code in your basket before you pay. You can use one code per order, and a code "
        "cannot be added after the order is placed.\n"
        "Codes do not apply to delivery costs, gift cards or items that are already reduced. The welcome code from "
        "our newsletter gives 10% off your first order over €50.\n"
        "Gift cards are valid for 3 years. You can check the balance in My account > Gift cards.",
    },
    {
        "id": "HC-20",
        "title": "Price drops after you order",
        "section": "Payments and invoices",
        "team": "billing",
        "body": "If the price of an item you bought goes down within 14 days of your order, we refund the difference "
        "once per item. Contact us with your order number and the item, and our billing team will check the price "
        "and refund the difference to your payment method.\n"
        "This does not apply to flash sales lasting less than 24 hours or to discount codes.",
    },
    {
        "id": "HC-21",
        "title": "Guarantee and warranty claims",
        "section": "Products",
        "team": "logistics",
        "body": "All our products come with a 2-year guarantee period from the delivery date. Sofa and bed frames "
        "have a 5-year guarantee.\n"
        "The guarantee covers manufacturing faults, not normal wear and tear, accidental damage or damage from "
        "incorrect assembly.\n"
        "To make a claim, use My account > Orders > Report a problem and add photos. If you ordered as a guest, use "
        "the contact form with your order number.",
    },
    {
        "id": "HC-22",
        "title": "Assembly instructions and assembly service",
        "section": "Products",
        "team": "logistics",
        "body": "Assembly instructions are in the box and can be downloaded as a PDF from the product page under "
        "Downloads. Most furniture takes 30 to 60 minutes to assemble with two people.\n"
        "In the Netherlands and Belgium, Brookhaul can assemble furniture when they deliver it. Assembly costs "
        "€49.00 per item and can be added in My account > Orders up to 2 days before delivery.\n"
        "Assembly is not available in other countries.",
    },
    {
        "id": "HC-23",
        "title": "Caring for your furniture and textiles",
        "section": "Products",
        "team": "logistics",
        "body": "Solid wood: wipe with a dry or slightly damp cloth and oil the surface every 6 to 12 months.\n"
        "Velvet and bouclé: vacuum with a soft brush, and treat stains straight away with a damp cloth.\n"
        "Linen: wash at 40 degrees, do not tumble dry, and iron while still damp.\n"
        "Rugs: vacuum weekly and turn them every 6 months to keep the colour even.\n"
        "Scented candles: trim the wick to 5 mm and never leave a lit candle unattended.",
    },
    {
        "id": "HC-24",
        "title": "Signing in and resetting your password",
        "section": "Account",
        "team": "tech",
        "body": "To reset your password, choose Forgot password on the sign-in (login) page and enter your email "
        "address. The "
        "reset link is valid for 24 hours. If the email does not arrive within a few minutes, check your spam "
        "folder.\n"
        "After 5 failed sign-in attempts, your account is locked for 30 minutes for your security. You can sign in "
        "again after that, or reset your password.\n"
        "Orders placed as a guest can be added to your account if you use the same email address.\n"
        "To change the email address of your account, go to My account > Details.",
    },
    {
        "id": "HC-25",
        "title": "Newsletters, marketing emails and your personal data",
        "section": "Account",
        "team": "tech",
        "body": "You can unsubscribe from our newsletter with the link at the bottom of every email, or in My "
        "account > Preferences. Changes take up to 48 hours.\n"
        "Requests to see, correct or delete the personal data we hold about you are handled by our privacy team at "
        "privacy@hollinvale.example. They answer within one month.\n"
        "Customer service cannot delete accounts or personal data by email or chat.",
    },
]
