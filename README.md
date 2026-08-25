# chudfish

Naive betting market arbitrage strategy

Polymarket had just introduced 15-min Crypto markets, and the liquidity was very low, so there was a small window of free arb. Likely could have made ~15/hr for about a month, but got sidetracked by a North American MTG Regional Championship.

Deployed it on EC2 with MongoDB backing database.

![Dashboard](/dashboard)

![Early-Dev Class Diagram](/earlyclassdiagram)


## Endpoints (localhost:5001)

```
/matched_market?market=market_name [GET, DELETE]
```

```
/matched_market [PUT, POST]

BODY:
{
    "name": "market_name", 
    "markets": 
    {
        "kalshi": "[uri]", 
        "polymarket":"[uri]"
    }
}
```

```
/list_matched_markets [GET]
```

```
/ticker [GET]
```
