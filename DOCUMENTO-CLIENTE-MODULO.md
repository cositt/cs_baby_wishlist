# Modulo `cs_baby_wishlist` - Documento funcional para cliente

## 1) Objetivo del modulo

`cs_baby_wishlist` permite que madres/padres creen y compartan listas de deseos de bebe desde la web de Odoo, sin usar el backend administrativo.

El modulo cubre:
- Creacion de listas por usuarios registrados en la web.
- Gestion de productos deseados.
- Comparticion por enlace publico.
- Compra de productos por terceros.
- Actualizacion automatica de cantidades compradas.
- Notificacion por email al padre/madre cuando una compra actualiza la lista.

---

## 2) Perfiles de uso

### A) Padre/Madre (usuario web registrado)
- Se registra e inicia sesion en la web.
- Crea una o varias listas.
- Gestiona sus listas (anade/quita productos).
- Comparte la lista con familiares/amigos.

### B) Invitado (sin login)
- Abre el enlace publico de una lista.
- Ve productos y cantidades.
- Puede comprar productos desde el ecommerce.

### C) Admin interno (backend Odoo)
- Tiene vista de control de listas en backend.
- Puede gestionar datos por soporte/operacion si hace falta.

---

## 3) Flujo completo del modulo (end-to-end)

## Paso 1 - Registro web del padre/madre
- El usuario se registra en `\`/web/signup\``.
- Inicia sesion en `\`/web/login\``.

## Paso 2 - Entrada desde "Mi cuenta"
En la pagina de cuenta (`\`/my\``) aparecen accesos directos:
- **Mis listas de bebe** -> `\`/my/baby-wishlist\``.
- **Crear nueva lista** -> `\`/my/baby-wishlist/new\``.

## Paso 3 - Creacion de lista
Desde `\`/baby-wishlist\``:
- Elige productos y cantidades.
- Completa datos de lista (nombre, fecha, notas, co-parent opcional).
- Guarda la lista.

Resultado:
- Se crea `wishlist.list` con lineas `wishlist.line`.
- Se generan 2 enlaces:
  - **Publico** para compartir.
  - **Privado de gestion** para editar sin backend.

## Paso 4 - Gestion de la lista
Desde `\`/wishlist/manage/<manage_token>\``:
- Ver productos actuales.
- Anadir productos.
- Quitar productos.
- Ir al catalogo para seguir anadiendo.

## Paso 5 - Anadir desde catalogo (`/shop`)
Cuando el usuario esta logueado:
- Boton `+ lista deseo` aparece en cada producto.
- Si tiene **1 sola lista activa**: anade directo.
- Si tiene **varias listas**: abre modal para elegir lista.

## Paso 6 - Comparticion con terceros
El padre/madre comparte `\`/wishlist/<token>\``.

En esa pagina publica:
- Se muestra nombre de lista.
- Productos con deseado/comprado/restante.
- Boton de compra por linea.

## Paso 7 - Compra por invitado
- Invitado pulsa comprar.
- Se redirige al carrito ecommerce.
- Se limita compra segun cantidad restante.

## Paso 8 - Actualizacion automatica de comprado
Al confirmar pedido de venta:
- El modulo actualiza `quantity_purchased` de la linea wishlist.
- Nunca supera `quantity_desired`.
- La linea pasa a "cumplida" cuando llega al deseado.
- Se envia email de actualizacion al padre/madre con el estado de productos comprados/restantes.

---

## 4) Funcionalidades principales implementadas

- Modelo de listas (`wishlist.list`) con estado y token.
- Modelo de lineas (`wishlist.line`) con control de cantidades.
- Enlace publico para visualizacion y compra.
- Enlace privado para gestion.
- Multi-lista por usuario.
- Integracion con tienda para anadir productos.
- Vista portal para acceso desde "Mi cuenta".
- Restricciones para no editar listas cerradas.
- Validaciones para evitar cantidades invalidas o sobrecompra.
- Email automatico al padre/madre cuando se confirma una compra que afecta a la lista.

---

## 5) Reglas de negocio relevantes

- Una lista cerrada no se puede modificar.
- No se puede comprar mas de lo restante.
- Cantidad comprada no puede superar deseada.
- El enlace publico es solo lectura + compra.
- El enlace privado permite gestionar sin backend.

---

## 6) Experiencia de usuario esperada

Para el padre/madre:
1. Entra a su cuenta.
2. Crea o abre una lista.
3. Anade productos desde lista o catalogo.
4. Comparte el enlace publico.

Para invitado:
1. Entra al enlace compartido.
2. Compra articulos.
3. El sistema actualiza progreso de la lista.

---

## 7) Que validar con cliente (checklist de alcance)

Usar este bloque en reunion para confirmar si vamos bien:

1. **Registro y acceso**
   - [ ] El registro web actual es suficiente.
   - [ ] No se requiere login social/externo en esta fase.

2. **Creacion de listas**
   - [ ] Crear desde web (no backend) es el flujo esperado.
   - [ ] El cliente necesita crear varias listas por usuario.

3. **Gestion de productos**
   - [ ] El boton en catalogo y modal de seleccion cubren la necesidad.
   - [ ] La UX de "1 lista = anadir directo" es correcta.

4. **Comparticion**
   - [ ] Enlace publico por token es el metodo de compartir deseado.
   - [ ] Enlace privado de gestion por token esta aceptado.

5. **Compra y stock de deseo**
   - [ ] La compra por terceros desde ecommerce cumple expectativa.
   - [ ] El control de cantidad restante es correcto.

6. **Comunicacion**
- [ ] Email de confirmacion al crear lista + email de actualizacion por compra son suficientes.
   - [ ] Se requiere (o no) plantilla de email personalizada con branding.

7. **Pendientes funcionales (si aplican)**
   - [ ] Permisos de co-parent (editar vs solo ver).
   - [ ] Caducidad o archivado automatico de listas.

---

## 8) Resumen ejecutivo

El modulo ya permite un flujo real de negocio para listas de bebe:
- Web-first para padres/madres.
- Comparticion simple por enlace.
- Compra asistida para invitados.
- Control de progreso de cada producto.

Este documento sirve para validar con cliente que el alcance funcional coincide con su necesidad antes de cerrar fase o seguir con mejoras.
