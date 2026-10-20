/* Click or tap a figure to enlarge it. Tap the enlarged image to toggle full-size panning. */
(function () {
    var imgs = document.querySelectorAll('figure img');
    if (!imgs.length || !window.HTMLDialogElement) return;

    var d = document.createElement('dialog');
    d.className = 'lb';
    d.setAttribute('aria-label', 'Image viewer');
    d.innerHTML =
        '<div class="lb-bar"><p class="lb-cap"></p>' +
        '<button type="button" class="lb-zoom" aria-pressed="false">Full size</button>' +
        '<button type="button" class="lb-close">Close</button></div>' +
        '<div class="lb-stage"><img alt=""></div>';
    document.body.appendChild(d);

    var stage = d.querySelector('.lb-stage'),
        big = stage.querySelector('img'),
        cap = d.querySelector('.lb-cap'),
        zoom = d.querySelector('.lb-zoom'),
        closeBtn = d.querySelector('.lb-close'),
        opener = null;

    function setZoom(on) {
        d.classList.toggle('is-zoomed', on);
        zoom.setAttribute('aria-pressed', on ? 'true' : 'false');
        zoom.textContent = on ? 'Fit to screen' : 'Full size';
        if (on) {
            stage.scrollLeft = (stage.scrollWidth - stage.clientWidth) / 2;
            stage.scrollTop = 0;
        }
    }

    function open(img, trigger) {
        var fc = img.closest('figure') && img.closest('figure').querySelector('figcaption');
        big.src = img.currentSrc || img.src;
        big.alt = img.alt;
        cap.textContent = fc ? fc.textContent.trim() : img.alt;
        opener = trigger;
        setZoom(false);
        document.body.classList.add('lb-open');
        d.showModal();
        closeBtn.focus();
    }

    Array.prototype.forEach.call(imgs, function (img) {
        var wrap = document.createElement('span');
        wrap.className = 'lb-wrap';
        img.parentNode.insertBefore(wrap, img);
        wrap.appendChild(img);
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'lb-open-btn';
        b.textContent = 'Enlarge';
        b.setAttribute('aria-label', 'Enlarge figure: ' + img.alt);
        wrap.appendChild(b);
        b.addEventListener('click', function () { open(img, b); });
        img.addEventListener('click', function () { open(img, b); });
    });

    big.addEventListener('click', function () { setZoom(!d.classList.contains('is-zoomed')); });
    zoom.addEventListener('click', function () { setZoom(!d.classList.contains('is-zoomed')); });
    closeBtn.addEventListener('click', function () { d.close(); });
    stage.addEventListener('click', function (e) { if (e.target === stage) d.close(); });
    d.addEventListener('click', function (e) { if (e.target === d) d.close(); });
    d.addEventListener('close', function () {
        document.body.classList.remove('lb-open');
        big.removeAttribute('src');
        if (opener) opener.focus();
    });
})();