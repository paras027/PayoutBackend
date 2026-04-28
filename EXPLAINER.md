# EXPLAINER.md

## 1. The Ledger
So, it was written in the document that we are not supposed to create a field called balance 
that means we have to write a query to calculate the balance. Now to calculate the balance we have to do one thing which is storing the credit/debit amount and then calculate the balance. I created model of ledger containing these fields->
1) Merchant -- as it will store and make relationship with merchant table
2) Amount -- it is basically the numerical value which is debited or credited
3) Type -- its the type like if the amount is debit or credit one... i chose added type insteda of defining credit and debit fields seperatly
            because it would have not made any sense as in at one time for 1 merchant either he will credit the amount or debit it. so if i created credit and debit as different fields then lets say user debit the amount then obviously i will set that amount in debit field but have to leave credit field null. So instead of making it complex i used the Type field
4) created_at -- Jo store the time it was created at

Note** -- i have created a list of tuple to have fields as credit or debit only and put it inside the Type so that user can only put credit or
          debit. If he puts something else then it will throw an error.

**Balance calculation query:**

balance = Ledger.objects.filter(merchant=merchant).aggregate(
                total_balance=Sum(
                    Case(
                        When(type='credit', then=F('amount')),
                        When(type='debit', then=-F('amount')),
                    )
                )
            )['total_balance'] or 0

## 2. The Lock

Code-- 
         with transaction.atomic():

            # Lock merchant row (concurrency)
            merchant = Merchant.objects.select_for_update().get(id=merchant.id)

            # Calculate balance
            balance = Ledger.objects.filter(merchant=merchant).aggregate(
                total_balance=Sum(
                    Case(
                        When(type='credit', then=F('amount')),
                        When(type='debit', then=-F('amount')),
                    )
                )
            )['total_balance'] or 0

            # Calculate held amount
            held = Payout.objects.filter(
                merchant=merchant,
                status__in=['pending', 'processing']
            ).aggregate(total=Sum('amount'))['total'] or 0

            available_balance = balance - held

            #Correct balance check
            if available_balance < amount:
                return Response({"error": "Insufficient balance"}, status=400)

            bank_account_id = request.data.get('bank_account_id', '')

            #Create payout
            payout = Payout.objects.create(
                merchant=merchant,
                amount=amount,
                status='pending',
                bank_account_id=bank_account_id
            )

            response_data = {
                "payout_id": payout.id,
                "amount": amount,
                "balance": balance
            }

            # Save idempotency key
            IdempotantKey.objects.create(
                merchant=merchant,
                key=key,
                response_data=response_data
            )

            # IMPORTANT → send task AFTER commit
            def send_task():
                process_payout.delay(payout.id)

            transaction.on_commit(send_task)

Explanation --  So basically what i have done is used the transaction.atomic() and  select_for_update() to handle concurrent requests. 
Transaction.atomic() makes sure that if anywhere in the code anything fails then everything we changed before that should get rolled back. Everything will be changed permanently only if the transaction is committed successfully.
select_for_update() locks the particular field so that when it is locked no other request coming simulataneously can access that field or write on it. This makes the data secured because if one request is made and is already accessing the data and changing it then the next request will most probably try to access the old data of that field if both the requests are done at same time.

Further Explanation -- So after accepting all the details like amount,merchant id, idempotency key and doing validation we move to the transaction part. First we will lock the field using select_for_update() and pass the id of merchant. Then we are calculcating the balance by doing SUM(and applying the case statement here like if type is credit then store amount and if its debit then store -amount) This will basically calculate sum. 
Then we will calculate held amount because lets say balance is 1000 and user 1 tries the debit of 300 from it now the process will go on till the transaction is commited. once it is commited it will be delegated to worker to perform it in async and there only it will update the Ledger table and add the debit thing. now transaction is completede so user  will request but he will see the balance as 1000 only because what if the worker is still processing the payment and has not updated the Ledger yet. so to fix that we taken the concept of holding money. So lets say like that 300 debit request from user is still pending in payout so we will filter it out and store it in held money. then we can do balance-held to check if amount requested by user 2 is in range of balance or not.
Next we will check and if balance-held is enough then we go and create payout of it and send it as pending. And then
set the idempotancy(will talk about it later). and then commit the transaction and send the task to queue of processing payment through worker.

## 3. The Idempotency
So here the logcal part was to remember the details of the last user who requested or made api call because if the same user makes the call again due to any reason it should not perform the operation if already done. So to fix it i had one solution which was to store user's details in the server but there was one issue like lets say a server crashes and it looses the data then the whole saved details will be wiped out. So i chose to save that in db to make it secured. Later on i got to know about this concept called Idempotency which takes merchant name,key and response data. So when someone does the payout thing it first checks that for that merchant and the key is the data stored inside Idempotancy DB or not. If yes then it will return the stored response data and if no then it will perform the whole operation.

**Code--**

existing_key = IdempotantKey.objects.filter(
    merchant=merchant,
    key=key,
    created_at__gte=timezone.now() - timedelta(hours=24)
).first()

if existing_key:
    return Response(existing_key.response_data, status=200)

----------------------------------------------------------------

## 4. The State Machine
So i did handled this part i mean i was confused about it first but later on got the idea of what is expected to be done. I have implemented a dictionary containing the key and there values.
lets say key is pending and value is processing that means if something is in pending state only that can move to processing state. I have defined that dictionary as Valid_transitions and then using a function we are checking that the current transition and new transition are key values in the Valid_transition or not. If not then throw the error else we can continue updating it. So everytime we have to update the status we will check if it is valid transition or not

**Codee--**

VALID_TRANSITIONS = {
    'pending': ['processing'],
    'processing': ['completed', 'failed'],
    'completed': [],
    'failed': []
}

def can_transition(current_status, new_status):
    return new_status in VALID_TRANSITIONS.get(current_status, [])

if not can_transition(payout.status, 'completed'):
    return  # blocks completed→anything, failed→completed, etc.

This is checked before every status change in `tasks.py`:

---

## 5. The AI Audit
So i was getting confused about the retry logic so asked AI for it but it gave me the code shown below. When i tried running it i found out that there is a problem in this code which is it is doing the retry thing twice. first it raises the exception then catch it again performs it. So i tried to research about it a bit more and came to the conclusion of removing that exception and just do the retry thing once only.

NOTE-- Infact i was also wondering that currently we are storing the number of retries locally but if server crashes then its sure it will loose all of its retry details so its better to store the attempts in DB.


**What AI gave me (wrong):**


try:
    result = random.random()
    if result < 0.7:
        ...
    elif result < 0.9:
        ...
    else:
        raise self.retry(countdown=5)

except Exception as e:
    raise self.retry(exc=e, countdown=5)



**What I replaced it with:**

countdown = 5 * (2 ** self.request.retries)
raise self.retry(countdown=countdown)


This gives backoffs of 5s, 10s, 20s across the 3 retry attempts instead of a flat 5s every time.

