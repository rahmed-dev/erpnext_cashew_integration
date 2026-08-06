(function () {
  var root = document.documentElement;
  var charts = {};

  function tok(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }
  function ramp() { return [tok('--c1'),tok('--c2'),tok('--c3'),tok('--c4'),tok('--c5'),tok('--c6'),tok('--c7'),tok('--c8'),tok('--c9'),tok('--c10')]; }

  // zrender parses colors itself and does not understand color-mix()
  function alpha(name, a) {
    var h = tok(name).replace('#', '');
    if (h.length === 3) h = h[0]+h[0]+h[1]+h[1]+h[2]+h[2];
    var n = parseInt(h, 16);
    if (isNaN(n)) return 'rgba(120,120,140,' + a + ')';
    return 'rgba(' + ((n>>16)&255) + ',' + ((n>>8)&255) + ',' + (n&255) + ',' + a + ')';
  }

  var fmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
  function money(v) { return fmt.format(Math.round(v)); }
  function compact(v) {
    var a = Math.abs(v);
    if (a >= 1e6) return (v/1e6).toFixed(a >= 1e7 ? 0 : 1) + 'M';
    if (a >= 1e3) return (v/1e3).toFixed(0) + 'k';
    return String(Math.round(v));
  }
  var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function monthLabel(m) { var p = m.split('-'); return MON[+p[1]-1] + " '" + p[0].slice(2); }

  /* ---------------- period windows ---------------- */
  var ALL = DATA.monthly.months.slice();
  var WINDOWS = {
    month: ALL.slice(-1),
    six: ALL.slice(-6),
    all: ALL
  };
  var current = 'all';

  function view(ms) {
    var set = {};
    ms.forEach(function (m) { set[m] = 1; });

    var idx = ms.map(function (m) { return DATA.monthly.months.indexOf(m); });
    var monthly = {
      months: ms,
      income: idx.map(function (i) { return DATA.monthly.income[i]; }),
      expense: idx.map(function (i) { return DATA.monthly.expense[i]; }),
      net: idx.map(function (i) { return DATA.monthly.net[i]; })
    };

    var kpi = { total_income: 0, total_expense: 0, si_count: 0, si_value: 0, pi_count: 0, pi_value: 0, je_count: 0, je_value: 0 };
    ms.forEach(function (m) {
      var k = DATA.by_month.kpi[m]; if (!k) return;
      kpi.total_income += k.inc; kpi.total_expense += k.exp;
      kpi.si_count += k.si_c; kpi.si_value += k.si_v;
      kpi.pi_count += k.pi_c; kpi.pi_value += k.pi_v;
      kpi.je_count += k.je_c; kpi.je_value += k.je_v;
    });
    kpi.net = kpi.total_income - kpi.total_expense;

    var cats = {};
    ms.forEach(function (m) {
      var d = DATA.by_month.expense_cats[m] || {};
      Object.keys(d).forEach(function (c) { cats[c] = (cats[c] || 0) + d[c]; });
    });
    var treemap = Object.keys(cats).map(function (c) { return { name: c, value: cats[c] }; })
      .sort(function (a, b) { return b.value - a.value; });

    var lk = {};
    ms.forEach(function (m) {
      var d = DATA.by_month.links[m] || {};
      Object.keys(d).forEach(function (key) { lk[key] = (lk[key] || 0) + d[key]; });
    });
    var nodeSet = {};
    var links = Object.keys(lk).filter(function (key) { return lk[key] > 0; }).map(function (key) {
      var p = key.split('|');
      nodeSet[p[0]] = 1; nodeSet[p[1]] = 1;
      return { source: p[0], target: p[1], value: lk[key] };
    });
    var sankey = { nodes: Object.keys(nodeSet).sort().map(function (n) { return { name: n }; }), links: links };

    var calendar = DATA.calendar.filter(function (d) { return set[d[0].slice(0, 7)]; });

    var bi = DATA.balance.months.map(function (m, i) { return set[m] ? i : -1; }).filter(function (i) { return i >= 0; });
    var bseries = {};
    DATA.balance.wallets.forEach(function (w) {
      bseries[w] = bi.map(function (i) { return DATA.balance.series[w][i]; });
    });
    var balance = {
      months: bi.map(function (i) { return DATA.balance.months[i]; }),
      wallets: DATA.balance.wallets,
      series: bseries,
      networth: bi.map(function (i) { return DATA.balance.networth[i]; })
    };

    // A cycle with no matching transactions is 0, not absent — a month where you
    // saved nothing is a missed target, not a missing data point.
    var budgets = DATA.budgets.map(function (b) {
      var lookup = {};
      b.months.forEach(function (m, i) { lookup[m] = b.actuals[i]; });
      return Object.assign({}, b, {
        months: ms.slice(),
        actuals: ms.map(function (m) { return lookup[m] || 0; })
      });
    });

    return { months: ms, monthly: monthly, kpi: kpi, treemap: treemap, sankey: sankey, calendar: calendar, balance: balance, budgets: budgets };
  }

  /* ---------------- chart plumbing ---------------- */
  function base() {
    return {
      animationDuration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 500,
      textStyle: { fontFamily: tok('--font') || 'sans-serif', color: tok('--text-muted'), fontSize: 11 },
      tooltip: {
        backgroundColor: tok('--surface'), borderColor: tok('--border-strong'), borderWidth: 1,
        padding: [7, 10], textStyle: { color: tok('--text'), fontSize: 12 },
        extraCssText: 'border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.12);'
      }
    };
  }
  function yAxisMoney() {
    return {
      type: 'value',
      axisLine: { lineStyle: { color: tok('--border-strong') } },
      axisTick: { show: false },
      axisLabel: { color: tok('--axis'), fontSize: 10, formatter: compact },
      splitLine: { lineStyle: { color: tok('--grid') } }
    };
  }
  function xAxisMonths(ms, every) {
    return {
      type: 'category', data: ms,
      axisLine: { lineStyle: { color: tok('--border-strong') } },
      axisTick: { show: false }, splitLine: { show: false },
      axisLabel: { color: tok('--axis'), fontSize: 10, formatter: monthLabel, interval: every === undefined ? 'auto' : every }
    };
  }
  function set(id, opt) {
    var el = document.getElementById(id);
    if (!el) return;
    if (!charts[id]) charts[id] = echarts.init(el, null, { renderer: 'canvas' });
    charts[id].setOption(opt, true);
  }
  function drop(id) {
    if (charts[id]) { charts[id].dispose(); delete charts[id]; }
  }

  /* ---------------- render ---------------- */
  function render() {
    var V = view(WINDOWS[current]);
    var multi = V.months.length > 1;
    var k = V.kpi, mo = V.monthly;

    document.getElementById('periodSub').textContent =
      (multi ? V.months[0] + ' → ' + V.months[V.months.length - 1] : monthLabel(V.months[0])) +
      ' · Code.Solutions · PKR';

    document.getElementById('kExpense').innerHTML = '<span class="ccy">PKR</span>' + money(k.total_expense);
    document.getElementById('kIncome').innerHTML = '<span class="ccy">PKR</span>' + money(k.total_income);
    document.getElementById('kNet').innerHTML = '<span class="ccy">PKR</span>' + money(k.net);
    document.getElementById('kInv').innerHTML = (k.si_count + k.pi_count) + '<span class="ccy" style="margin-left:6px">docs</span>';
    document.getElementById('kInvFoot').innerHTML =
      '<span class="pill up">' + k.si_count + ' sales · ' + compact(k.si_value) + '</span>' +
      '<span class="pill down">' + k.pi_count + ' purchase · ' + compact(k.pi_value) + '</span>';
    document.getElementById('kJe').textContent = k.je_count + ' journal entries below threshold';

    function delta(arr) {
      var n = arr.length; if (n < 2) return null;
      var h = Math.floor(n / 2);
      var recent = arr.slice(h).reduce(function (a, b) { return a + b; }, 0);
      var prior = arr.slice(0, h).reduce(function (a, b) { return a + b; }, 0);
      if (!prior) return null;
      return Math.round((recent - prior) / prior * 100);
    }
    [['kExpenseTrend', mo.expense], ['kIncomeTrend', mo.income]].forEach(function (pair) {
      var d = delta(pair[1]), el = document.getElementById(pair[0]);
      el.textContent = d === null ? '—' : (d >= 0 ? '+' : '') + d + '%';
    });

    function spark(id, arr, color) {
      if (!multi) { drop(id); document.getElementById(id).innerHTML = ''; return; }
      set(id, Object.assign(base(), {
        grid: { left: 0, right: 0, top: 3, bottom: 0 },
        xAxis: { type: 'category', boundaryGap: false, data: mo.months, show: false },
        yAxis: { type: 'value', show: false, min: Math.min.apply(null, arr.concat([0])) },
        tooltip: Object.assign(base().tooltip, {
          trigger: 'axis',
          formatter: function (p) { return monthLabel(p[0].axisValue) + '<br><b>PKR ' + money(p[0].data) + '</b>'; }
        }),
        series: [{
          type: 'line', data: arr, smooth: 0.35, symbol: 'none',
          lineStyle: { width: 1.6, color: tok(color) },
          areaStyle: { color: alpha(color, 0.16) },
          markPoint: {
            symbol: 'circle', symbolSize: 5, silent: true, label: { show: false },
            itemStyle: { color: tok(color) },
            data: [{ coord: [mo.months.length - 1, arr[arr.length - 1]] }]
          }
        }]
      }));
    }
    spark('sparkExpense', mo.expense, '--expense');
    spark('sparkIncome', mo.income, '--income');
    spark('sparkNet', mo.net, '--accent');

    /* income vs expense */
    set('cTrend', Object.assign(base(), {
      grid: { left: 46, right: 14, top: 28, bottom: 38 },
      legend: { top: 0, right: 0, itemWidth: 9, itemHeight: 9, itemGap: 14, textStyle: { color: tok('--text-muted'), fontSize: 11 } },
      tooltip: Object.assign(base().tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: alpha('--accent', 0.07) } },
        formatter: function (ps) {
          var s = '<div style="font-weight:600;margin-bottom:4px">' + monthLabel(ps[0].axisValue) + '</div>';
          ps.forEach(function (p) {
            s += '<div style="display:flex;gap:10px;justify-content:space-between"><span>' + p.marker + p.seriesName +
              '</span><b style="font-variant-numeric:tabular-nums">' + money(Math.abs(p.data)) + '</b></div>';
          });
          return s;
        }
      }),
      xAxis: xAxisMonths(mo.months, multi && mo.months.length > 8 ? 1 : 0),
      yAxis: yAxisMoney(),
      series: [
        { name: 'Income', type: 'bar', stack: 'a', data: mo.income, itemStyle: { color: tok('--income'), borderRadius: [3,3,0,0] }, barMaxWidth: 26 },
        { name: 'Expense', type: 'bar', stack: 'a', data: mo.expense.map(function (v) { return -v; }), itemStyle: { color: tok('--expense'), borderRadius: [0,0,3,3] }, barMaxWidth: 26 },
        { name: 'Net', type: 'line', data: mo.net, smooth: 0.3, symbol: 'circle', symbolSize: 4, lineStyle: { width: 2, color: tok('--accent') }, itemStyle: { color: tok('--accent') }, z: 3 }
      ]
    }));

    /* ---- budgets: cycle count decides the treatment (D3.d) ---- */
    var goalB = V.budgets.filter(function (b) { return b.income && !b.archived && b.months.length; })[0];
    var limitB = V.budgets.filter(function (b) { return !b.income && !b.archived && b.months.length; })[0];

    var goalTitle = document.getElementById('goalTitle');
    var goalSub = document.getElementById('goalSub');
    var goalScope = document.getElementById('goalScope');
    var goalCard = document.getElementById('goalCard');

    if (!goalB) {
      goalCard.style.display = 'none';
      drop('cGauge');
    } else {
      goalCard.style.display = '';
      var cycles = goalB.months.length;
      goalTitle.textContent = goalB.name;
      goalScope.innerHTML =
        '<span><span class="swatch" style="background:var(--income)"></span>' + goalB.wallets.join(', ') + '</span>' +
        '<span><span class="swatch" style="background:var(--c2)"></span>' + goalB.categories.join(', ') + '</span>';

      if (cycles > 1) {
        var hit = goalB.actuals.filter(function (v) { return v >= goalB.amount; }).length;
        goalSub.textContent = 'Monthly budget · ' + hit + ' of ' + cycles + ' cycles met · target PKR ' + money(goalB.amount);
        set('cGauge', Object.assign(base(), {
          grid: { left: 46, right: 14, top: 14, bottom: 34 },
          tooltip: Object.assign(base().tooltip, {
            trigger: 'axis',
            formatter: function (ps) {
              var v = ps[0].data, d = v - goalB.amount;
              return '<div style="font-weight:600;margin-bottom:3px">' + monthLabel(ps[0].axisValue) + '</div>' +
                'Saved <b>PKR ' + money(v) + '</b><br>Target PKR ' + money(goalB.amount) + '<br>' +
                '<span style="color:' + (d >= 0 ? tok('--income') : tok('--expense')) + '">' +
                (d >= 0 ? 'Met, +' + money(d) : 'Short by ' + money(-d)) + '</span>';
            }
          }),
          xAxis: xAxisMonths(goalB.months),
          yAxis: yAxisMoney(),
          series: [{
            type: 'bar', data: goalB.actuals, barMaxWidth: 24,
            itemStyle: {
              borderRadius: [3,3,0,0],
              color: function (p) { return p.data >= goalB.amount ? tok('--income') : tok('--transfer'); }
            },
            markLine: {
              silent: true, symbol: 'none',
              lineStyle: { color: tok('--income'), width: 1, type: 'dashed' },
              label: { formatter: 'target ' + compact(goalB.amount), color: tok('--text-faint'), fontSize: 10, position: 'insideEndTop' },
              data: [{ yAxis: goalB.amount }]
            }
          }]
        }));
      } else {
        var actual = goalB.actuals[0], pct = Math.round(actual / goalB.amount * 100);
        goalSub.textContent = 'Monthly budget · ' + monthLabel(goalB.months[0]);
        set('cGauge', Object.assign(base(), {
          series: [{
            type: 'gauge', startAngle: 210, endAngle: -30, min: 0, max: 100,
            radius: '94%', center: ['50%', '62%'],
            progress: { show: true, width: 13, roundCap: true, itemStyle: { color: pct >= 100 ? tok('--income') : tok('--accent') } },
            axisLine: { lineStyle: { width: 13, color: [[1, tok('--grid')]] } },
            pointer: { show: false }, axisTick: { show: false }, splitLine: { show: false },
            axisLabel: { show: false }, anchor: { show: false },
            title: { offsetCenter: [0, '34%'], color: tok('--text-faint'), fontSize: 11 },
            detail: { offsetCenter: [0, '-2%'], color: tok('--text'), fontSize: 26, fontWeight: 600, formatter: function () { return pct + '%'; } },
            data: [{ value: Math.min(pct, 100), name: 'PKR ' + compact(actual) + ' of ' + compact(goalB.amount) }]
          }]
        }));
      }
    }

    var limitCard = document.getElementById('limitCard');
    if (!limitB) {
      limitCard.style.display = 'none';
      drop('cBudget');
    } else {
      limitCard.style.display = '';
      var over = limitB.actuals.filter(function (v) { return v > limitB.amount; }).length;
      document.getElementById('limitSub').textContent =
        limitB.name + ' · ' + limitB.categories.join(', ') + ' on ' + limitB.wallets.join(', ') +
        ' · limit PKR ' + money(limitB.amount) +
        (limitB.months.length > 1 ? ' · over in ' + over + ' of ' + limitB.months.length + ' cycles' : '');
      set('cBudget', Object.assign(base(), {
        grid: { left: 46, right: 14, top: 16, bottom: 34 },
        tooltip: Object.assign(base().tooltip, {
          trigger: 'axis',
          formatter: function (ps) {
            var v = ps[0].data, d = v - limitB.amount;
            return '<div style="font-weight:600;margin-bottom:3px">' + monthLabel(ps[0].axisValue) + '</div>' +
              'Spent <b>PKR ' + money(v) + '</b><br>Limit PKR ' + money(limitB.amount) + '<br>' +
              '<span style="color:' + (d > 0 ? tok('--expense') : tok('--income')) + '">' +
              (d > 0 ? 'Over by ' + money(d) : 'Under by ' + money(-d)) + '</span>';
          }
        }),
        xAxis: xAxisMonths(limitB.months),
        yAxis: yAxisMoney(),
        series: [{
          type: 'bar', data: limitB.actuals, barMaxWidth: 26,
          itemStyle: {
            borderRadius: [3,3,0,0],
            color: function (p) { return p.data > limitB.amount ? tok('--expense') : tok('--income'); }
          },
          markLine: {
            silent: true, symbol: 'none',
            lineStyle: { color: tok('--text-faint'), width: 1, type: 'dashed' },
            label: { formatter: 'limit ' + compact(limitB.amount), color: tok('--text-faint'), fontSize: 10, position: 'insideEndTop' },
            data: [{ yAxis: limitB.amount }]
          }
        }]
      }));
    }

    /* net worth */
    var bal = V.balance;
    set('cNetworth', Object.assign(base(), {
      grid: { left: 50, right: 14, top: 16, bottom: 34 },
      tooltip: Object.assign(base().tooltip, {
        trigger: 'axis',
        formatter: function (ps) { return monthLabel(ps[0].axisValue) + '<br><b>PKR ' + money(ps[0].data) + '</b>'; }
      }),
      xAxis: Object.assign(xAxisMonths(bal.months, bal.months.length > 8 ? 2 : 0), { boundaryGap: false }),
      yAxis: yAxisMoney(),
      series: [{
        type: 'line', data: bal.networth, smooth: 0.3,
        symbol: bal.months.length === 1 ? 'circle' : 'none', symbolSize: 6,
        lineStyle: { width: 2, color: tok('--accent') },
        itemStyle: { color: tok('--accent') },
        areaStyle: {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
            { offset: 0, color: alpha('--accent', 0.30) },
            { offset: 1, color: alpha('--accent', 0.02) }
          ] }
        },
        markLine: {
          silent: true, symbol: 'none', label: { show: false },
          lineStyle: { color: tok('--expense'), width: 1, type: 'dashed' },
          data: [{ yAxis: 0 }]
        }
      }]
    }));

    /* balance by account */
    set('cAccounts', Object.assign(base(), {
      grid: { left: 50, right: 14, top: 24, bottom: 34 },
      legend: { top: 0, left: 0, itemWidth: 8, itemHeight: 8, itemGap: 9, textStyle: { color: tok('--text-muted'), fontSize: 10 } },
      tooltip: Object.assign(base().tooltip, {
        trigger: 'axis',
        formatter: function (ps) {
          var s = '<div style="font-weight:600;margin-bottom:4px">' + monthLabel(ps[0].axisValue) + '</div>';
          ps.slice().sort(function (a, b) { return b.data - a.data; }).forEach(function (p) {
            if (!p.data) return;
            s += '<div style="display:flex;gap:12px;justify-content:space-between"><span>' + p.marker + p.seriesName +
              '</span><b style="font-variant-numeric:tabular-nums">' + money(p.data) + '</b></div>';
          });
          return s;
        }
      }),
      xAxis: Object.assign(xAxisMonths(bal.months, bal.months.length > 8 ? 2 : 0), { boundaryGap: false }),
      yAxis: yAxisMoney(),
      series: bal.wallets.map(function (w, i) {
        return {
          name: w, type: 'line', stack: 'bal', data: bal.series[w], smooth: 0.25,
          symbol: bal.months.length === 1 ? 'circle' : 'none',
          lineStyle: { width: 1 }, itemStyle: { color: ramp()[i % 10] }, areaStyle: { opacity: 0.72 }
        };
      })
    }));

    /* treemap */
    set('cTreemap', Object.assign(base(), {
      tooltip: Object.assign(base().tooltip, {
        formatter: function (p) {
          var share = k.total_expense ? (p.value / k.total_expense * 100).toFixed(1) : '0';
          return '<b>' + p.name + '</b><br>PKR ' + money(p.value) + '<br><span style="color:' + tok('--text-faint') + '">' + share + '% of spend</span>';
        }
      }),
      series: [{
        type: 'treemap', roam: false, nodeClick: false, breadcrumb: { show: false },
        top: 2, left: 2, right: 2, bottom: 2,
        itemStyle: { borderColor: tok('--surface'), borderWidth: 2, gapWidth: 2, borderRadius: 4 },
        label: {
          show: true, color: '#fff', fontSize: 11.5, fontWeight: 550, lineHeight: 14,
          formatter: function (p) { return (k.total_expense && p.value / k.total_expense > 0.028) ? p.name + '\n' + compact(p.value) : ''; }
        },
        data: V.treemap.map(function (d, i) { return { name: d.name, value: d.value, itemStyle: { color: ramp()[i % 10] } }; })
      }]
    }));

    /* calendar */
    var years = {};
    V.calendar.forEach(function (d) { years[d[0].slice(0, 4)] = 1; });
    var ys = Object.keys(years).sort();
    var vals = V.calendar.map(function (d) { return d[1]; }).sort(function (a, b) { return a - b; });
    var vmax = vals[Math.floor(vals.length * 0.94)] || 1;
    set('cCalendar', Object.assign(base(), {
      tooltip: Object.assign(base().tooltip, {
        formatter: function (p) { return p.data[0] + '<br><b>PKR ' + money(p.data[1]) + '</b>'; }
      }),
      visualMap: {
        min: 0, max: vmax, type: 'continuous', orient: 'horizontal',
        left: 'center', bottom: 0, itemWidth: 10, itemHeight: 90,
        text: [compact(vmax) + '+', '0'], textStyle: { color: tok('--text-faint'), fontSize: 10 },
        inRange: { color: [tok('--accent-50'), tok('--accent'), tok('--accent-700')] },
        calculable: false
      },
      calendar: ys.map(function (y, i) {
        return {
          top: 26 + i * (ys.length > 1 ? 128 : 40), left: 34, right: 12, cellSize: ['auto', ys.length > 1 ? 15 : 20],
          range: multi ? y : V.months[0],
          itemStyle: { color: tok('--surface-2'), borderColor: tok('--surface'), borderWidth: 2 },
          splitLine: { show: false },
          yearLabel: { show: ys.length > 1, color: tok('--text-faint'), fontSize: 11, margin: 26 },
          monthLabel: { color: tok('--axis'), fontSize: 10 },
          dayLabel: { color: tok('--axis'), fontSize: 9, nameMap: ['S','M','T','W','T','F','S'] }
        };
      }),
      series: ys.map(function (y, i) {
        return {
          type: 'heatmap', coordinateSystem: 'calendar', calendarIndex: i,
          data: V.calendar.filter(function (d) { return multi ? d[0].slice(0,4) === y : true; }),
          itemStyle: { borderRadius: 2, borderColor: tok('--surface'), borderWidth: 2 }
        };
      })
    }));

    /* sankey */
    set('cSankey', Object.assign(base(), {
      tooltip: Object.assign(base().tooltip, {
        trigger: 'item',
        formatter: function (p) {
          if (p.dataType === 'edge') return p.data.source + ' → ' + p.data.target + '<br><b>PKR ' + money(p.data.value) + '</b>';
          return '<b>' + p.name + '</b><br>PKR ' + money(p.value);
        }
      }),
      series: [{
        type: 'sankey', top: 8, bottom: 8, left: 8, right: 92,
        nodeWidth: 11, nodeGap: 9, draggable: false,
        emphasis: { focus: 'adjacency' },
        label: { color: tok('--text-muted'), fontSize: 11 },
        lineStyle: { color: 'gradient', opacity: 0.34, curveness: 0.5 },
        data: V.sankey.nodes.map(function (n, i) { return { name: n.name, itemStyle: { color: ramp()[i % 10], borderWidth: 0 } }; }),
        links: V.sankey.links
      }]
    }));
  }

  /* ---------------- chrome ---------------- */
  var m = DATA.meta;
  document.getElementById('foot').innerHTML =
    'Rendered from your real backup <code>' + m.source + '</code> — ' + m.txns +
    ' paid transactions (' + m.ops + ' income/expense, ' + m.transfers +
    ' transfers). USD rows converted at a flat ' + m.usd_pkr +
    ' for this demo only; the real dashboard uses each row&rsquo;s actual transacted rate. ' +
    'Invoice split mirrors the live routing rule: income &rarr; Sales Invoice, expense at or above the threshold &rarr; Purchase Invoice, below it &rarr; Journal Entry. ' +
    'The savings goal and spending limit are your real Cashew budgets, matched by category, account and direction. ' +
    'Switch the period to see the one-cycle treatment (gauge) versus the multi-cycle treatment (bars per cycle).';

  document.querySelectorAll('[data-window]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      current = btn.getAttribute('data-window');
      document.querySelectorAll('[data-window]').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b === btn));
      });
      render();
    });
  });

  document.getElementById('themeBtn').addEventListener('click', function () {
    var cur = root.getAttribute('data-theme');
    if (!cur) cur = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    root.setAttribute('data-theme', cur === 'dark' ? 'light' : 'dark');
    requestAnimationFrame(render);
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
    if (!root.getAttribute('data-theme')) requestAnimationFrame(render);
  });

  var t;
  addEventListener('resize', function () {
    clearTimeout(t);
    t = setTimeout(function () {
      Object.keys(charts).forEach(function (id) { charts[id].resize(); });
    }, 120);
  });

  render();
})();
