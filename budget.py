#!/usr/bin/python

import sqlite3
import argparse

def db_exec(f):
    con = sqlite3.connect('budget.sqlite3')
    con.cursor().execute('PRAGMA foreign_keys = ON')
    cur = con.cursor()
    ret = f(con, cur)
    con.commit()
    con.close()
    return ret

def float2int(f):
    return int(round(f, 2) * 100)

def int2currency(i):
    return f'${i / 100:,.2f}'

def print_table(table, alignments):
    widths = []
    for n in range(len(table[0])):
        widths.append(0)

    for row in table:
        for n in range(len(row)):
            widths[n] = max(widths[n], len(str(row[n])))

    for r in range(len(table)):
        for n in range(len(table[r])):
            alignment = '<' if alignments[n] == 'left' else '>'
            print(f'{table[r][n]:{alignment}{widths[n]}} ',end='')
        print()
        if r == 0:
            print('-' * sum([w + 1 for w in widths]))

def month_id():
    def f(con, cur):
        id = cur.execute('select id from month where name=:budget',
                         args.__dict__).fetchone()
        if not id:
            print(f'No month {args.budget!r}.')
            return
        else:
            return id[0]

    return db_exec(f)
        
def category_id(month_id):
    def f(con, cur):
        args.month = month_id
        id = cur.execute('select id from category where name=:category and month=:month',
                         args.__dict__).fetchone()
        if not id:
            print(f'No category {args.category!r}.')
            return
        else:
            return id[0]

    return db_exec(f)
        
parser = argparse.ArgumentParser()
parser.add_argument(
    'budget', type=str,
    help='string to identify the month, example: 22-01')
subparsers = parser.add_subparsers(title='actions')

view = subparsers.add_parser('view')

def handle_view(args):
    def f(con, cur):
        args.month = month_id()
        if not args.month: return
            
        incomes = cur.execute('select name, amount from income where month=:month',
                               args.__dict__).fetchall()
        if not incomes:
            print('You need to add at least one source of income.')
            return

        sum_income = sum([income[1] for income in incomes])
        incomes = [(name, f'{int2currency(amount)}') for name, amount in incomes]

        incomes.insert(0, ('income', f'{int2currency(sum_income)}'))
        print_table(incomes, ('left', 'right'))

        print()

        rows = cur.execute(
            'select name, type, budget, '
            '(select sum(value) '
            'from expense '
            'where category=category.id) as curr ' 
            'from category '
            'where month=(select id from month where name=:budget)',
            args.__dict__).fetchall()
        if not rows:
            print('no categories')
            return
            
        categories = {}
        sums = {}
        sum_budget = sum_curr = sum_diff = 0
        for name, type, value, curr in rows:
            if not type in categories: categories[type] = []
            if not type in sums: sums[type] = [0,0,0]
            if curr == None: curr = 0
            diff = value - curr
            sum_budget += value
            sum_curr += curr
            sum_diff += diff
            categories[type].append((name, value, curr, diff))
            sums[type][0] += value
            sums[type][1] += curr
            sums[type][2] += diff

        flat_categories = [('category', 'budget', 'account', 'diff')]
        for type in categories:
            flat_categories.append(
                (f'[{type}]', int2currency(sums[type][0]),
                 int2currency(sums[type][1]), int2currency(sums[type][2])))
            
            for row in map(lambda row: (row[0], int2currency(row[1]), int2currency(row[2]),
                                        int2currency(row[3])), categories[type]):
                flat_categories.append(row)
            flat_categories.append(('','','',''))
        flat_categories.append(('total',
            int2currency(sum_budget), int2currency(sum_curr), int2currency(sum_diff)))
        print_table(flat_categories, ('left', 'right', 'right', 'right'))
        
        balances = [('balance',''),
                    ('budget', int2currency(sum_income - sum_budget)),
                    ('account', int2currency(sum_income - sum_curr))]
        print()
        print_table(balances, ('left','right'))
        
        budgets = [('budget','%/income')]
        for type in categories:
            budgets.append(
                (type, f'{sum([category[1] for category in categories[type]]) / sum_income:2.2%}'))
        print()
        print_table(budgets, ('left','right'))
            
    db_exec(f)
    
view.set_defaults(func=handle_view)

category = subparsers.add_parser('category')
category_actions = category.add_subparsers(title='category',
                                           help='additional help')
category_new = category_actions.add_parser('new')
category_new.add_argument(
    'name', type=str,
    help='category\'s name, example: fuel, phone or groceries')
category_new.add_argument(
    'type', type=str,
    help='category\'s group, example: essential, want or investings')
category_new.add_argument(
    'amount', type=float,
    help='amount is rounded and stored with two decimals')

def handle_category_new(args):
    def f(con,cur):
        args.month = month_id()
        if not args.month: return

        args.amount = float2int(args.amount)
        try:
            cur.execute('insert into category (name,type,budget,month)'
                        'values (:name,:type,:amount,:month)',
                        args.__dict__)
        except sqlite3.IntegrityError as e:
            print(f'Error, maybe there is already a category called '
                  f'{args.name!r} at {args.budget!r}.')
            return
        
        print(f'new category {args.name}@{args.type} '
              f'with budget equal to {int2currency(args.amount)}')
    db_exec(f)
    
category_new.set_defaults(func=handle_category_new)

category_view = category_actions.add_parser('view')

def handle_category_view(args):
    def f(con, cur):
        args.month = month_id()
        if not args.month: return
        
        categories = cur.execute(
            'select name, budget, type '
            'from category '
            'where month=:month',
            args.__dict__).fetchall()
        if not categories:
            print('no categories')
            return
        
        categories = [(name, int2currency(amount), type)
                      for name, amount, type in categories]
        categories.insert(0, ('category', 'amount', 'type'))
        print_table(categories, ('left','right','left'))
        
    db_exec(f)
    
category_view.set_defaults(func=handle_category_view)

category_delete = category_actions.add_parser('delete')
category_delete.add_argument(
    'name', type=str)

def handle_category_delete(args):
    args.month = month_id()
    if not args.month: return
    
    def f(con, cur):
        cur.execute('delete from category where name=:name and month=:month',
                    args.__dict__)
        print(f'category {args.name!r} has been deleted.')
        
    db_exec(f)
    
category_delete.set_defaults(func=handle_category_delete)

expense = subparsers.add_parser('expense')
expense_actions = expense.add_subparsers(title='expense',
                                         help='additional help')
expense_new = expense_actions.add_parser('new')
expense_new.add_argument(
    'category', type=str,
    help='expense\'s category, example: fuel, phone or groceries')
expense_new.add_argument(
    'amount', type=float,
    help='amount is rounded and stored with two decimals')

def handle_expense_new(args):
    def f(con, cur):
        args.month = month_id()
        if not args.month: return

        category = args.category
        args.category = category_id(args.month)
        if not args.category: return
        
        amount = args.amount
        args.amount = float2int(args.amount)
        cur.execute('insert into expense (value,category) '
                    'values (:amount,:category)',
                    args.__dict__)
        print(f"new expense {int2currency(args.amount)}@{category} ")
        
    db_exec(f)

expense_new.set_defaults(func=handle_expense_new)

income = subparsers.add_parser('income')
income_actions = income.add_subparsers(title='income',
                                       help='additional help')
income_new = income_actions.add_parser('new')
income_new.add_argument(
    'name', type=str,
    help='name of the income source, example: salary')
income_new.add_argument(
    'amount', type=float,
    help='amount is rounded and stored with two decimals')

def handle_income_new(args):
    args.month = month_id()
    if not args.month: return

    args.amount = float2int(args.amount)
    def f(con, cur):
        cur.execute('insert into income (name,amount,month) '
                    'values (:name,:amount,:month)',
                    args.__dict__)
        print(f"new income {args.name!r} equal to {int2currency(args.amount)}")
        
    db_exec(f)

income_new.set_defaults(func=handle_income_new)

income_view = income_actions.add_parser('view')

def handle_income_view(args):
    def f(con, cur):
        args.month = month_id()
        if not args.month: return
        
        incomes = cur.execute('select name, amount from income '
                              'where month=:month',
                              args.__dict__).fetchall()
        if not incomes:
            print('no incomes')
            return

        incomes = [(name, int2currency(amount)) for name, amount in incomes]
        incomes.insert(0, ('name','amount'))                    
        print_table(incomes, ('left','right'))
        
    db_exec(f)
    
income_view.set_defaults(func=handle_income_view)

income_delete = income_actions.add_parser('delete')
income_delete.add_argument(
    'name', type=str)

def handle_income_delete(args):
    def f(con, cur):
        cur.execute('delete from income where name=:name', args.__dict__)
        print(f'income {args.name!r} has been deleted.')
        
    db_exec(f)
    
income_delete.set_defaults(func=handle_income_delete)

month = subparsers.add_parser('month')
month_actions = month.add_subparsers(title='month')
month_new = month_actions.add_parser('new')

def handle_month_new(args):
    def f(con, cur):
        cur.execute('insert or ignore into month (name) values (:budget)',
                    args.__dict__)
        print(f'new month {args.budget!r}')
    db_exec(f)
    
month_new.set_defaults(func=handle_month_new)

month_delete = month_actions.add_parser('delete')

def handle_month_delete(args):
    def f(con, cur):
        cur.execute('delete from month where name=:budget', args.__dict__)
        print(f'month {args.budget!r} has been deleted')
    db_exec(f)
    
month_delete.set_defaults(func=handle_month_delete)

parser.set_defaults(func=lambda args: parser.print_help())

args = parser.parse_args()
args.func(args)
