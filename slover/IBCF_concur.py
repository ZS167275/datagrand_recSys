# coding=utf-8
import os
from itertools import permutations
import math
import pickle as pickle
import pandas as pd
import time

"""
    去掉已经view的

"""

def get_action_weight( x):
    if x == 'view': return 1
    if x == 'deep_view': return 5
    if x == 'share':return 10
    if x == 'comment': return 5
    if x == 'collect':return 15
    else:return 1

def get_rating_matrix(  ):
    path = '../cache/rating_all.pkl'
    if os.path.exists(path):
        train = pickle.load(open(path, "rb"))
    else:
        end = time.mktime(time.strptime('2017-2-18 22:00:00', '%Y-%m-%d %H:%M:%S'))

        train = pd.read_csv('../data/train.csv')
        train = train[['user_id', 'item_id', 'action_type']]
        item_display = pd.read_csv('../data/item_display.csv')
        item_display['end_time'] = item_display['end_time'].apply( lambda x: time.mktime(time.strptime(x, '%Y%m%d %H:%M:%S')) )
        # 选择距end时间2小时内被view过的，其余的训练集item假定已经失去了时效，不再推荐
        news = item_display[ (item_display['end_time']>=end) ][['item_id']] #10216
        train = pd.merge(train, news, on='item_id')[['user_id','item_id','action_type']]

        train['weight'] = train['action_type'].apply( get_action_weight )
        train = train[['user_id','item_id','weight']].groupby( ['user_id','item_id'],as_index=False ).sum()
        pickle.dump( train,open(path,'wb'),True ) #dump 时如果指定了 protocol 为 True，压缩过后的文件的大小只有原来的文件的 30%
    return train

def get_concur_mat(  ):
    path = "../cache/concur_mat.pkl"
    if os.path.exists(path):
        sim_mat = pickle.load(open(path, "rb"))
    else:
        rat_mat = get_rating_matrix()
        sim_mat = pd.DataFrame()
        item1_list = []
        item2_list = []
        concur_count = []
        user_groups = rat_mat.groupby( ['user_id'] )
        for name,group in user_groups:
            for pair in permutations(list(group['item_id'].values), 2):
                item1_list.append( pair[0] )
                item2_list.append( pair[1] )
                concur_count.append( 1 )
            # print name
        sim_mat['item1'] = item1_list
        sim_mat['item2'] = item2_list
        sim_mat['count'] = concur_count
        sim_mat = sim_mat.groupby(['item1', 'item2'], as_index=False).sum()
        pickle.dump(sim_mat, open(path, 'wb'), True)
    return sim_mat

def get_concur_sim(  ):
    path = "../cache/concur_sim_mat.pkl"
    if os.path.exists(path):
        sim_mat = pickle.load(open(path, "rb"))
    else:
        concur_mat = get_concur_mat()
        rat_mat = get_rating_matrix()
        item_vector = rat_mat[['item_id','user_id']].groupby(['item_id'],as_index=False).count()
        item_vector.index = item_vector['item_id']
        item_vector.columns = ['item_id','count']
        item_count_dict = item_vector['count'].to_dict()
        concur_mat['item1_count'] = concur_mat['item1'].apply( lambda p:item_count_dict[p] )
        concur_mat['item2_count'] = concur_mat['item2'].apply(lambda p: item_count_dict[p])
        concur_mat['sim'] = concur_mat['count'] / (concur_mat['item1_count'].apply(math.sqrt) * concur_mat['item2_count'].apply(math.sqrt))

        sim_mat = pd.DataFrame()
        for item1,group in concur_mat.groupby( ['item1'],as_index=False ):
            df = group.sort_values( ['sim'],ascending=False ).head( 20 )
            sim_mat = sim_mat.append( df )
        pickle.dump(sim_mat, open(path, 'wb'), True)
    return sim_mat[['item1','item2','sim']]

def help( p ):
    ss = str(p).split(",")
    rec,viewed = ss[0],ss[1]
    rec = list( rec.split(" ") )
    viewed_list = list( set( viewed.split(" ") ) )
    size = 0
    for i in rec:
        size += 1
        if i in viewed_list:
            rec.remove( i )
            size -= 1
        if size == 5:break

    rec = " ".join(rec[:5])
    return rec

def Recommendation_s( k=5):
    train = pd.read_csv('../data/train.csv')
    train['item_id'] = train['item_id'].apply(str)
    print('计算评分矩阵')
    rate_mat = get_rating_matrix()
    rate_mat['item_id'] = rate_mat['item_id'].apply(str)
    print('计算相似度')
    iid_iid_sim = get_concur_sim()
    iid_iid_sim['item1'] = iid_iid_sim['item1'].apply(str)
    iid_iid_sim['item2'] = iid_iid_sim['item2'].apply(str)
    user_list = []
    viewed_list = []
    for user, group in train[['user_id', 'item_id']].groupby(['user_id']):
        user_list.append(user)
        viewed_list.append(" ".join(list(group['item_id'].values)))
    user_viewed = pd.DataFrame()
    user_viewed['user_id'] = user_list
    user_viewed['item_id'] = viewed_list

    rec = pd.DataFrame()
    user_list = []
    rec_items_list = []
    users = pd.read_csv('../data/candidate.txt')
    df = pd.merge(users, rate_mat, on='user_id')
    df = pd.merge(df, iid_iid_sim, left_on='item_id', right_on='item1')
    df['score'] = df['weight'] * df['sim']
    df = df[['user_id', 'item2', 'score']].sort_values(['user_id', 'score'], ascending=False)
    print('为每个用户推荐')
    for user_id, group in df.groupby(['user_id'], as_index=False, sort=False):
        rec_items = " ".join(map(str, list(group['item2'].head(15).values)))

        user_list.append(user_id)
        rec_items_list.append(rec_items)
        # print('------------------------')
    rec['user_id'] = user_list
    rec['item_id'] = rec_items_list

    print('还有部分的冷启动用户,推荐18时之后的topHot20')
    train_h18 = train[train.action_time >= time.mktime(time.strptime('2017-2-18 18:00:00', '%Y-%m-%d %H:%M:%S'))]
    topHot = \
    train_h18.groupby(['item_id'], as_index=False).count().sort_values(['action_time'], ascending=False).head(15)[
        'item_id'].values
    oldrec = users
    oldrec['oldrec_item'] = [" ".join(list(topHot))] * len(oldrec)
    oldrec = pd.merge(oldrec, rec, how='left', on='user_id', ).fillna(0)
    oldrec = oldrec[oldrec.item_id == 0][['user_id', 'oldrec_item']]
    oldrec.columns = ['user_id', 'item_id']
    rec = rec.append(oldrec)

    print('过滤掉用户已经看过的')
    rec = pd.merge(rec, user_viewed, how='left', on='user_id').fillna("")  # item_view
    rec['item_id'] = rec['item_id_x'] + "," + rec['item_id_y']
    rec['item_id'] = rec['item_id'].apply(help)
    rec = rec[['user_id', 'item_id']]

    rec.drop_duplicates('user_id').to_csv('../result/result.csv', index=None, header=None) #0.006795


Recommendation_s()
