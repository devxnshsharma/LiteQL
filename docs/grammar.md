# LiteQL grammar

```
query        ::= "SELECT" column_list "FROM" STRING [where_clause] [order_clause] [limit_clause]
column_list  ::= "*" | column ("," column)*
column       ::= IDENTIFIER
where_clause ::= "WHERE" condition
condition    ::= comparison (("AND" | "OR") comparison)*
comparison   ::= column OP value
order_clause ::= "ORDER BY" column ["ASC" | "DESC"]
limit_clause ::= "LIMIT" INTEGER
value        ::= STRING | NUMBER | column
```

The grammar does not specify precedence between `AND` and `OR`. LiteQL evaluates a mixed condition left-to-right, matching the grammar's repeated sequence. Parentheses are outside scope.
