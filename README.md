# La Tienda de Don Pepe

Aplicación web en español basada en el documento de gestión de abarrotes y servicios. Python 3.12+, SQLite y JavaScript; no necesita paquetes externos.

## Ejecutar

```sh
cd /workspace/tiendaanggie
python3 app.py
```

Puerto predeterminado 8000, escucha local. `HOST`, `PORT` y `ANGGIE_DB` permiten cambiar host, puerto y ubicación de SQLite. Para un servidor accesible desde otra máquina, configurar `HOST=0.0.0.0` únicamente detrás de un proxy HTTPS y con acceso controlado.

En el primer ingreso se crea la cuenta de administrador (contraseña mínima de 10 caracteres). No hay credenciales predeterminadas. Incluye los 100 productos/presentaciones indicados por el dueño en `catalog/productos.csv`, con precios en soles y stock, costo y mínimo iniciales en cero. Registra compras y configura mínimos antes de vender. El catálogo reemplaza al anterior una sola vez al arrancar; conserva como archivados los productos con historial y elimina los demás. No modifica precios o existencias en arranques posteriores. La base se guarda en `data/anggie.db`, excluida de Git.

## Funciones implementadas

- Interfaz lila con login renovado, opción de mostrar contraseña y modo claro/oscuro persistente.
- Autenticación con hash scrypt, sesiones de ocho horas y permisos verificados en el servidor. Roles administrador, ventas, compras y servicios. Creación y desactivación de usuarios.
- Catálogo por producto/presentación, precios, costo promedio, mínimo y alertas de stock. Edición del catálogo.
- Compras al contado con proveedor y ventas con múltiples productos. Actualización transaccional de inventario, validación de existencias y movimientos.
- Clientes, proveedores, ventas fiadas, historial y abonos que no pueden superar el saldo.
- Empresas/operadores, recargas y recibos pendientes; confirmación manual externa, referencias únicas por empresa, fallidos y anulación administrativa con motivo.
- Registro de recargas y recibos pagados exclusivamente por Yape o transferencia bancaria, con número de operación del pago opcional y banco obligatorio para transferencias. Los formularios distinguen recargas (operador y celular, sin periodo) de recibos (empresa, suministro o cuenta y periodo opcional), muestran una sola comisión de la tienda y calculan el total a cobrar. No requiere saldo prepagado. Los registros antiguos conservan sus datos y su control de saldo anterior. Una anulación interna no simula una devolución.
- Resumen y reportes exclusivos de administrador: filtros por fecha, ventas, compras, margen bruto histórico y comisiones separadas. Exportación de resumen CSV y constancias internas imprimibles con destino de servicio enmascarado.

Los servicios se registran; **no se ejecutan recargas ni pagos reales**. Las empresas de agua/luz son ejemplos configurables. El catálogo maneja cada presentación como una existencia independiente; no convierte automáticamente sacos a arrobas o unidades base.

## Verificar

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Las pruebas usan bases temporales: compra/venta, stock, fiados, abonos, confirmación y anulación de servicios, contraseñas, acceso y permisos HTTP. La interfaz permite conservar el tema seleccionado entre sesiones del navegador.

## Respaldo

```sh
python3 backup.py
```

Genera una copia consistente, incluso con la aplicación activa. Programar este comando diariamente con el planificador del servidor y copiar los respaldos a un almacenamiento seguro separado. `ANGGIE_BACKUPS` cambia el destino. Para restaurar: detener la aplicación, conservar una copia de la base actual, sustituirla por un respaldo y arrancar de nuevo. La programación y el almacenamiento remoto no están configurados.

## Alcance pendiente antes de uso comercial

Esta es una primera versión funcional, no la implementación completa de los 38 requisitos. Faltan recuperación de acceso, conversiones entre presentaciones, integración API con proveedor, múltiples cuentas de plataforma, reversiones externas y devoluciones conciliadas, correcciones/anulación de ventas, edición de clientes/proveedores, comprobantes tributarios, reportes detallados adicionales y respaldo periódico automatizado. Las constancias de venta actuales muestran el resumen, sin detalle de artículos.

Antes de exponerla a Internet: desplegar con servidor/proxy de producción y HTTPS, cookies Secure, limitación de intentos de login, gestión persistente de sesiones y recuperación segura de cuentas, revisar seguridad y configurar copias externas. Las sesiones actuales se pierden al reiniciar. No se ha publicado ni desplegado el sistema.
