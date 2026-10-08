# Anotações sobre pendencias futuras que precisam ser feitas

- [x] Como devemos tratar a atualização de senha no endpoint PUT /v1/producers/{id}?
  -> Concluído: Senha mantida imutável no PUT cadastral. Implementada a rota dedicada `POST /v1/auth/password` com validação de senha atual via bcrypt, suportando produtores e consultores.

- 