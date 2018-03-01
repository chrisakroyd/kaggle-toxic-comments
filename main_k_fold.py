import keras.backend as K

# Only use the amount of memory we require rather than the maximum
if 'tensorflow' == K.backend():
    import tensorflow as tf
    from keras.backend.tensorflow_backend import set_session
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    config.gpu_options.visible_device_list = "0"
    set_session(tf.Session(config=config))

from keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau

# Utility code.
from src.callbacks import RocAucEvaluation
from src.load_data import load_data_folds, load_test_data, load_sample_submission
from src.load_glove_embeddings import load_embedding_matrix
from src.write_results import write_results
from src.util import get_save_path
# Model definition
from src.models.bidirectional_GRU_conc_pool import BidirectionalGRUConcPool

TRAIN = True
WRITE_RESULTS = True
MAX_FEATS = 200000
SEQUENCE_LENGTH = 150
NUM_FOLDS = 10

# Paths to data sets
train_path = './data/train.csv'
test_path = './data/test.csv'
submission_path = './data/sample_submission.csv'
# Paths to glove embeddings.
glove_path = './data/embeddings/glove.42B.300d.txt'
glove_embed_dims = 300


(x_train, y_train), folds, word_index, num_classes, tokenizer = load_data_folds(path=train_path,
                                                                                folds=NUM_FOLDS,
                                                                                max_features=MAX_FEATS,
                                                                                sequence_length=SEQUENCE_LENGTH)

embedding_matrix = load_embedding_matrix(glove_path=glove_path,
                                         word_index=word_index,
                                         embedding_dimensions=glove_embed_dims)

vocab_size = len(word_index) + 1

model_instance = BidirectionalGRUConcPool(num_classes=num_classes)

print('Number of Data Samples:' + str(len(x_train)))
print('Number of Classes: ' + str(num_classes))

if TRAIN:
    early_stop = EarlyStopping(monitor='val_loss',
                               patience=2,
                               verbose=1,
                               min_delta=0.00001)

    reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.1,
                                  patience=1,
                                  verbose=1,
                                  epsilon=0.0001,
                                  mode='min', min_lr=0.0001)

    model = model_instance.build(vocab_size,
                                 embedding_matrix,
                                 input_length=x_train.shape[1],
                                 embed_dim=glove_embed_dims,
                                 summary=False)
    # Store initial weights
    init_weights = model.get_weights()

    for i, (train, test) in enumerate(folds):
        print('Fold:' + str(i + 1))
        f_x_train, f_y_train = x_train[train], y_train[train]
        x_val, y_val = x_train[test], y_train[test]

        roc_auc = RocAucEvaluation(validation_data=(x_val, y_val), interval=1)
        checkpoint = ModelCheckpoint(get_save_path(model_instance, fold=i), save_best_only=True)

        model.fit(x=f_x_train,
                  y=f_y_train,
                  validation_data=(x_val, y_val),
                  epochs=model_instance.EPOCHS,
                  batch_size=model_instance.BATCH_SIZE,
                  callbacks=[early_stop, roc_auc, checkpoint])

        model.set_weights(init_weights)

    model = None
    K.clear_session()

if WRITE_RESULTS:
    test_set = load_test_data(test_path, tokenizer, sequence_length=SEQUENCE_LENGTH)

    submission = load_sample_submission(submission_path)
    write_results(model_instance, test_set, submission, folds=NUM_FOLDS)