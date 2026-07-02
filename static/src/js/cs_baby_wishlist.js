/*
 * Reubica el modal "+ lista deseo" al <body> antes de abrirlo.
 *
 * El modal se inyecta con xpath dentro de #product_option_block, cuyo ancestro
 * (carrusel/zoom de imagen de la ficha de producto) usa CSS `transform`. Un
 * transform crea un containing block que atrapa el `position: fixed` de los
 * modales Bootstrap, dejando el modal por detras de la imagen y sin poder
 * confirmar. Moverlo a <body> lo saca de ese contexto de apilamiento.
 */
document.addEventListener("show.bs.modal", function (ev) {
    var modal = ev.target;
    if (
        modal &&
        modal.classList &&
        modal.classList.contains("cs-wishlist-modal") &&
        modal.parentElement !== document.body
    ) {
        document.body.appendChild(modal);
    }
});
