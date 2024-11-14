from graph_data import GoTermDataset, collate_fn
from torch.utils.data import DataLoader
from network import CL_protNET
import torch
from sklearn import metrics
from utils import log, PR_metrics, fmax
import argparse
import pickle as pkl
from config import get_config
import numpy as np
from joblib import Parallel, delayed
import os
#os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

def test(config, task, model_pt, test_type='test'):
    print(config.device)
    test_set = GoTermDataset(test_type,task,ood=config.ood)
    test_loader = DataLoader(test_set, batch_size=config.batch_size, shuffle=False, collate_fn=collate_fn)
    output_dim = test_set.y_true.shape[-1]
    model = CL_protNET(output_dim, config.esmembed, config.pooling).to(config.device)
    model.load_state_dict(torch.load(model_pt,map_location=config.device))
    model.eval()
    bce_loss = torch.nn.BCELoss()
    with open("./data/child_mx.pkl", "rb") as f:
        mx = pkl.load(f)
    child_mx = torch.tensor(mx[task],dtype=torch.float32).to(config.device)
    output_dim = test_set.y_true.shape[-1]
    
    y_pred_all = []

    y_true_all = test_set.y_true.float()
    with torch.no_grad():
        for idx_batch, batch in enumerate(test_loader):
            y_pred,_= model(batch[0].to(config.device),child_mx=child_mx)
            y_pred_all.append(y_pred)
        y_pred_all = torch.cat(y_pred_all, dim=0).cpu()

        eval_loss = bce_loss(y_pred_all, y_true_all)
        
        Fmax = fmax(y_true_all.numpy(), y_pred_all.numpy(),100 )
        aupr = metrics.average_precision_score(y_true_all.numpy(), y_pred_all.numpy(), average='samples')
        log(f"Test ||| loss: {round(float(eval_loss),3)} ||| aupr: {round(float(aupr),3)} ||| Fmax: {round(float(Fmax),3)}" )
    
    if test_type == 'AF2test' and config.ood:
        result_name = config.test_result_path + 'AF2'+ model_pt[12:-3] + '_ood.pkl'
    elif test_type == 'AF2test' and not config.ood:
        result_name = config.test_result_path + 'AF2'+ model_pt[12:-3] + '_id.pkl'
    elif config.ood:
        result_name = config.test_result_path + model_pt[12:-3] + '_ood.pkl'
    else:
        result_name = config.test_result_path + model_pt[12:-3] + '_id.pkl'
    with open(result_name, "wb") as f:
        pkl.dump([y_pred_all.numpy(), y_true_all.numpy()], f)

def str2bool(v):
    if isinstance(v,bool):
        return v
    if v == 'True' or v == 'true':
        return True
    if v == 'False' or v == 'false':
        return False

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--task', type=str, default='bp', choices=['bp','mf','cc'], help='')
    p.add_argument('--device', type=str, default='', help='')
    p.add_argument('--model', type=str, default='', help='')
    p.add_argument('--esmembed', default=True, type=str2bool, help='')
    p.add_argument('--pooling', default='MTP', type=str, choices=['MTP','GMP'], help='Multi-set transformer pooling or Global mean pooling')
    p.add_argument('--AF2test', default=False, type=str2bool, help='')
    p.add_argument('--ood', default=True, type=str2bool, help='')
    #p.add_argument('--esm1b',type=str2bool,default=True)
    
    args = p.parse_args()
    print(args)
    config = get_config()
    config.batch_size = 32 
    #os.environ["CUDA_VISIBLE_DEVICES"] = args.device
    if args.device != '':
        config.device = "cuda:" + args.device
    config.esmembed = args.esmembed
    config.pooling = args.pooling
    config.ood = args.ood
    #config.esm1b = args.esm1b
    if not args.AF2test:
        test(config, args.task, args.model)
    else:
        test(config, args.task, args.model, 'AF2test')
