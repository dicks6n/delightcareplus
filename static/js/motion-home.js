/* Home page animations, built with Motion (motion.dev, the library behind Framer Motion).
 *
 *  - Hero: products spring in, then cycle through best sellers with blur/scale/tilt swaps,
 *    follow the mouse (parallax), float, and drift away as you scroll.
 *  - Banner slideshow (Seller Center → Home banners): wipe transition, Ken Burns zoom,
 *    staggered text, swipe, autoplay with progress bars.
 *  - Sections, product cards, brand tiles and categories reveal as they scroll into view.
 *
 * Everything stays usable without Motion (or with "reduce motion" on): the slideshow
 * switches instantly and nothing is hidden.
 *
 * Note: starting poses are written as plain styles and every animation gives explicit
 * [from, to] keyframes — a zero-length Motion animation used as a "set" makes the next
 * animation on that element jump straight to its end.
 */
(function () {
    const M = window.Motion;
    const root = document.documentElement;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const animated = !!M && !reduce;

    const $ = (sel, el) => (el || document).querySelector(sel);
    const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
    const springy = { type: 'spring', stiffness: 140, damping: 18 };
    const soft = { type: 'spring', stiffness: 90, damping: 20 };
    const px = (v) => (typeof v === 'number' ? v + 'px' : v);

    // Write a starting pose as plain styles (no animation)
    const set = (els, v) => [].concat(els).forEach(el => {
        const t = [];
        if (v.x !== undefined) t.push(`translateX(${px(v.x)})`);
        if (v.y !== undefined) t.push(`translateY(${px(v.y)})`);
        if (v.scale !== undefined) t.push(`scale(${v.scale})`);
        if (v.rotate !== undefined) t.push(`rotate(${v.rotate}deg)`);
        if (t.length) el.style.transform = t.join(' ');
        if (v.opacity !== undefined) el.style.opacity = v.opacity;
        if (v.filter !== undefined) el.style.filter = v.filter;
    });
    // After a reveal, hand styles back to the stylesheet so CSS hover effects work again
    const release = (els) => [].concat(els).forEach(el => { el.style.transform = ''; el.style.filter = ''; el.style.opacity = ''; });

    if (animated) root.classList.add('motion-on');

    /* ------------------------------------------------------------------ HERO */
    const stage = $('[data-hero-stage]');
    const copy = $('[data-hero-copy]');
    const slots = stage ? $$('.hero-product', stage) : [];
    const tags = stage ? $$('.hero-tag', stage) : [];

    if (animated && copy) {
        const lines = Array.from(copy.children);
        set(lines, { opacity: 0, y: 28, filter: 'blur(6px)' });
        M.animate(lines, { opacity: [0, 1], y: [28, 0], filter: ['blur(6px)', 'blur(0px)'] },
            { ...soft, delay: M.stagger(0.09) }).then(() => release(lines));
    }

    if (animated && slots.length) {
        slots.forEach((slot, i) => {
            const tilt = [-10, 8, -6][i] || 0;
            set(slot, { opacity: 0, y: 40, scale: 0.6, rotate: tilt });
            M.animate(slot, { opacity: [0, 1], y: [40, 0], scale: [0.6, 1], rotate: [tilt, 0] },
                { type: 'spring', stiffness: 110, damping: 13, delay: 0.25 + i * 0.14 });
            // Each card floats on its own rhythm
            M.animate($('.hp-float', slot), { y: [0, -12, 0], rotate: [0, i % 2 ? 1.2 : -1.2, 0] },
                { duration: 5.5 + i * 0.8, repeat: Infinity, ease: 'easeInOut', delay: 1.2 + i * 0.4 });
        });

        tags.forEach((tag, i) => {
            const from = i % 2 ? 40 : -40;
            set(tag, { opacity: 0, x: from });
            M.animate(tag, { opacity: [0, 1], x: [from, 0] }, { ...springy, delay: 0.9 + i * 0.18 });
        });

        // Mouse parallax: deeper cards move more
        const hero = stage.closest('.hero') || stage;
        if (matchMedia('(hover: hover)').matches) {
            hero.addEventListener('pointermove', (e) => {
                const r = hero.getBoundingClientRect();
                const dx = (e.clientX - r.left) / r.width - 0.5;
                const dy = (e.clientY - r.top) / r.height - 0.5;
                slots.forEach(slot => {
                    const d = parseFloat(slot.dataset.depth || 1);
                    M.animate(slot, { x: dx * 36 * d, y: dy * 26 * d }, { type: 'spring', stiffness: 80, damping: 16 });
                });
            });
            hero.addEventListener('pointerleave', () => M.animate(slots, { x: 0, y: 0 }, soft));
        }

        // Scroll: the product stack drifts down and fades as the hero leaves the screen
        M.scroll(M.animate(stage, { y: [0, 90], opacity: [1, 0.25] }, { ease: 'linear' }),
            { target: hero, offset: ['start start', 'end start'] });
    }

    // Cycle the hero photos through the best-seller pool
    const poolEl = document.getElementById('heroPool');
    const pool = poolEl ? JSON.parse(poolEl.textContent) : [];
    if (animated && slots.length && pool.length > slots.length) {
        const showing = slots.map((s, i) => i);          // which pool item each slot shows
        let nextItem = slots.length, nextSlot = 0, busy = false, visible = true;

        M.inView(stage, () => { visible = true; return () => { visible = false; }; });

        const swap = () => {
            if (busy || !visible || document.hidden) return;
            busy = true;
            const slot = slots[nextSlot];
            const item = pool[nextItem];
            const holder = $('.hp-float', slot);
            const oldImg = $('img', holder);
            const img = new Image();
            img.alt = '';
            img.src = item.img;
            const tilt = nextSlot % 2 ? -6 : 6;
            const ready = img.decode ? img.decode().catch(() => {}) : Promise.resolve();
            ready.then(() => {
                set(img, { opacity: 0, scale: 1.25, rotate: tilt, filter: 'blur(14px)' });
                holder.appendChild(img);
                slot.href = item.url;
                M.animate(oldImg, { opacity: [1, 0], scale: [1, 0.85], rotate: [0, -tilt], filter: ['blur(0px)', 'blur(10px)'] },
                    { duration: 0.6, ease: [0.4, 0, 0.2, 1] }).then(() => oldImg.remove());
                M.animate(img, { opacity: [0, 1], scale: [1.25, 1], rotate: [tilt, 0], filter: ['blur(14px)', 'blur(0px)'] },
                    { type: 'spring', stiffness: 100, damping: 15, delay: 0.12 });
                // A little "breath" on the card itself
                M.animate(slot, { scale: [1, 0.95, 1.02, 1] }, { duration: 0.9, ease: 'easeInOut' });
                showing[nextSlot] = nextItem;
                // Next item that isn't already on screen
                do { nextItem = (nextItem + 1) % pool.length; } while (showing.includes(nextItem));
                nextSlot = (nextSlot + 1) % slots.length;
                setTimeout(() => { busy = false; }, 900);
            });
        };
        setTimeout(() => setInterval(swap, 3200), 2600);
    }

    /* ------------------------------------------------------- BANNER SLIDESHOW */
    const show = $('[data-banner-show]');
    if (show) {
        const slides = $$('.banner-slide', show);
        const dots = $$('.banner-dots button', show);
        const DURATION = 6;   // seconds per slide
        const EASE = [0.77, 0, 0.18, 1];
        let index = 0, timer = null, paused = false, busy = false, kenBurns = null, progress = null;
        let remaining = 0, startedAt = 0;

        const setA11y = () => slides.forEach((s, i) => {
            s.classList.toggle('is-active', i === index);
            s.setAttribute('aria-hidden', i === index ? 'false' : 'true');
            s.tabIndex = i === index ? 0 : -1;
        });
        const setDots = () => {
            if (progress) { progress.stop(); progress = null; }
            dots.forEach((d, i) => {
                d.classList.toggle('on', i === index);
                // Reset through Motion so its next frame doesn't write the old value back
                if (animated && i !== index) M.animate($('span', d), { '--p': 0 }, { duration: 0.25 });
            });
        };

        const schedule = (ms) => {
            remaining = ms; startedAt = Date.now();
            clearTimeout(timer);
            if (!paused) timer = setTimeout(() => go(index + 1, 1), ms);
        };

        // dir = direction we arrived from (0 for the first slide): the photo settles in, then keeps a slow Ken Burns drift
        const startSlide = (dir) => {
            const img = $('.banner-img', slides[index]);
            if (animated) {
                kenBurns && kenBurns.stop();
                kenBurns = dir
                    ? M.animate(img, { scale: [1.3, 1.08, 1.18], x: [dir > 0 ? '6%' : '-6%', '0%', '-2%'] },
                        { duration: DURATION + 2, times: [0, 0.16, 1], ease: [[0.22, 1, 0.36, 1], 'linear'] })
                    : M.animate(img, { scale: [1.08, 1.18], x: ['0%', '-2%'] }, { duration: DURATION + 2, ease: 'linear' });
                if (paused) kenBurns.pause();
            }
            clearTimeout(timer);
            if (slides.length < 2 || reduce) return;
            const bar = dots[index] && $('span', dots[index]);
            if (animated && bar) {
                if (progress) progress.stop();
                progress = M.animate(bar, { '--p': [0, 1] }, { duration: DURATION, ease: 'linear' });
                if (paused) progress.pause();
            }
            schedule(DURATION * 1000);
        };
        const pause = () => {
            if (paused) return;
            paused = true;
            clearTimeout(timer);
            remaining -= Date.now() - startedAt;
            progress && progress.pause();
            kenBurns && kenBurns.pause();
        };
        const resume = () => {
            if (!paused) return;
            paused = false;
            progress && progress.play();
            kenBurns && kenBurns.play();
            schedule(Math.max(remaining, 400));
        };

        const go = (to, dir) => {
            to = (to + slides.length) % slides.length;
            if (to === index || busy) return;
            const from = slides[index], next = slides[to];
            const fromImg = $('.banner-img', from);
            index = to;
            setDots();
            if (!animated) { setA11y(); startSlide(0); return; }

            busy = true;
            next.style.zIndex = 2;
            next.style.visibility = 'visible';
            const copyEls = Array.from($('.banner-copy', next).children);
            set(copyEls, { opacity: 0, y: 30 });

            // Wipe the new slide in from the direction of travel; the old photo slides away
            const hidden = dir > 0 ? 'inset(0% 0% 0% 100%)' : 'inset(0% 100% 0% 0%)';
            next.style.clipPath = hidden;
            M.animate(next, { clipPath: [hidden, 'inset(0% 0% 0% 0%)'] }, { duration: 0.9, ease: EASE });
            kenBurns && kenBurns.stop();
            M.animate(fromImg, { x: dir > 0 ? '-8%' : '8%', opacity: [1, 0.4] }, { duration: 0.9, ease: EASE });
            M.animate(copyEls, { opacity: [0, 1], y: [30, 0] }, { ...springy, delay: M.stagger(0.1, { startDelay: 0.45 }) });
            startSlide(dir);

            setTimeout(() => {
                // Reset the slide we left so it's ready for next time
                set(fromImg, { x: '0%', scale: 1.08, opacity: 1 });
                next.style.zIndex = ''; next.style.visibility = ''; next.style.clipPath = '';
                setA11y();
                busy = false;
            }, 950);
        };

        $$('.banner-nav', show).forEach(b => b.addEventListener('click', () => go(index + Number(b.dataset.dir), Number(b.dataset.dir))));
        dots.forEach(d => d.addEventListener('click', () => {
            const to = Number(d.dataset.go);
            go(to, to > index ? 1 : -1);
        }));

        // Swipe on phones
        let downX = null, swiped = false;
        show.addEventListener('pointerdown', e => { downX = e.clientX; swiped = false; });
        show.addEventListener('pointerup', e => {
            if (downX === null) return;
            const dx = e.clientX - downX;
            downX = null;
            if (Math.abs(dx) > 50) { swiped = true; go(index + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1); }
        });
        // A swipe shouldn't also open the banner link
        show.addEventListener('click', e => { if (swiped) { e.preventDefault(); swiped = false; } }, true);

        show.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') pause(); });
        show.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') resume(); });
        show.addEventListener('focusin', pause);
        show.addEventListener('focusout', resume);
        document.addEventListener('visibilitychange', () => (document.hidden ? pause() : resume()));

        if (animated) {
            // First slide: text rises in once the slideshow is on screen
            const first = Array.from($('.banner-copy', slides[0]).children);
            set(first, { opacity: 0, y: 30 });
            let started = false;
            M.inView(show, () => {
                if (started) return;
                started = true;
                M.animate(first, { opacity: [0, 1], y: [30, 0] }, { ...springy, delay: M.stagger(0.1) });
                startSlide(0);
            }, { amount: 0.4 });
        } else {
            startSlide(0);
        }
    }

    /* --------------------------------------------------------- SCROLL REVEALS */
    if (animated) {
        $$('[data-reveal]').forEach(el => {
            set(el, { opacity: 0, y: 30 });
            M.inView(el, () => {
                M.animate(el, { opacity: [0, 1], y: [30, 0] }, soft).then(() => release(el));
            }, { amount: 0.3 });
        });

        $$('[data-reveal-group]').forEach(group => {
            const items = Array.from(group.children);
            const photos = items.map(i => $('.p-media img:not(.alt), img.bg, img', i)).filter(Boolean);
            set(items, { opacity: 0, y: 46, scale: 0.94 });
            set(photos, { scale: 1.25, filter: 'blur(8px)' });
            M.inView(group, () => {
                M.animate(items, { opacity: [0, 1], y: [46, 0], scale: [0.94, 1] }, { ...springy, delay: M.stagger(0.07) })
                    .then(() => release(items));
                M.animate(photos, { scale: [1.25, 1], filter: ['blur(8px)', 'blur(0px)'] },
                    { duration: 1.1, ease: [0.22, 1, 0.36, 1], delay: M.stagger(0.07) })
                    .then(() => release(photos));
            }, { amount: 0.15 });
        });
    }

    // Starting poses are set, so show the page (CSS kept things hidden until now)
    root.classList.remove('motion-pending');
})();
